# src/utils/report_generator.py
import os
import webbrowser
from pathlib import Path
from jinja2 import Template
from playwright.sync_api import sync_playwright

REGRESSION_TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{{ report_title | default('Reporte General de Ejecución') }}</title>
    <style>
        @page {
            size: A4 portrait;
            margin: 10mm;
        }

        {{ custom_css }}

        .report-metadata {
            margin-top: 10px;
            font-size: 0.95em;
            color: #d1d5db;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .report-metadata span {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .test-card, .kpi-container {
            break-inside: avoid;
        }
    </style>
</head>
<body>

    <div class="endpoint-header">
        <h2><span class="method-badge">{{ http_method }}</span> {{ endpoint_path }}</h2>

        <div class="report-metadata">
            <span><strong>Comparativa:</strong> {{ reference_source }} ↔ {{ target_env }}</span>
            {% if execution_date != 'N/A' %}
            <span>📅 <strong>Fecha:</strong> {{ execution_date }}</span>
            <span>⏱️ <strong>Hora:</strong> {{ execution_time }} hs</span>
            {% endif %}
            {% if total_suite_duration %}
            <span>⚡ <strong>Duración Suite:</strong> {{ total_suite_duration }}</span>
            {% endif %}
        </div>
    </div>

    <div class="kpi-container">
        <div class="kpi-card">
            <span>Casos Ejecutados</span>
            <div class="kpi-value">{{ total_scenarios }}</div>
        </div>
        <div class="kpi-card success">
            <span>Coincidencia General</span>
            <div class="kpi-value">{{ coincidence_percentage }}%</div>
        </div>
        <div class="kpi-card {% if failed_rules > 0 %}danger{% else %}success{% endif %}">
            <span>Validaciones a Verificar</span>
            <div class="kpi-value">{{ failed_rules }} Alerta(s)</div>
        </div>
        {% if avg_response_time is defined %}
        <div class="kpi-card warning">
            <span>Tiempo Promedio</span>
            <div class="kpi-value">{{ avg_response_time }} ms</div>
        </div>
        {% endif %}
    </div>

    <h3>📋 Resultados por Caso de Prueba</h3>

    <div class="filter-container">
        <button class="filter-btn active" onclick="filterResults(this, 'ALL')">Todos ({{ total_scenarios }})</button>
        <button class="filter-btn btn-passed" onclick="filterResults(this, 'PASSED')">Passed ({{ total_scenarios - failed_rules }})</button>
        <button class="filter-btn btn-failed" onclick="filterResults(this, 'FAILED')">Failed ({{ failed_rules }})</button>
    </div>

    <div id="test-results-list">
        {% for test in test_results %}
        <div class="test-card" data-status="{{ test.status }}">
            <div class="test-header">
                <h4>
                    <span class="badge {% if test.status == 'PASSED' %}bg-pass{% else %}bg-fail{% endif %}">{{ test.status }}</span>
                    {{ test.name }}
                </h4>

                {% if test.response_time_ms is defined %}
                <span class="time-badge {% if test.response_time_ms > 1000 %}slow{% else %}fast{% endif %}">
                    ⏱️ {{ test.response_time_ms }} ms
                </span>
                {% endif %}
            </div>

            <p>{{ test.description }}</p>

            {% if test.status == 'FAILED' and test.error_log %}
            <pre>{{ test.error_log }}</pre>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <script>
        function filterResults(buttonElement, status) {
            const buttons = document.querySelectorAll('.filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            buttonElement.classList.add('active');

            const cards = document.querySelectorAll('.test-card');
            cards.forEach(card => {
                if (status === 'ALL') {
                    card.style.display = 'block';
                } else {
                    const cardStatus = card.getAttribute('data-status');
                    card.style.display = (cardStatus === status) ? 'block' : 'none';
                }
            });
        }

        window.onscroll = function() {
            const btn = document.getElementById("scrollToTopBtn");
            if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {
                btn.classList.add("show");
            } else {
                btn.classList.remove("show");
            }
        };

        function scrollToTop() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }
    </script>

    <button id="scrollToTopBtn" onclick="scrollToTop()" title="Volver arriba">▲</button>
</body>
</html>
"""


COMPARISON_TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{{ report_title | default('Reporte de Comparación PROD vs DEV') }}</title>
    <style>
        @page {
            size: A4 portrait;
            margin: 10mm;
        }

        {{ custom_css }}

        .report-metadata {
            margin-top: 10px;
            font-size: 0.95em;
            color: #d1d5db;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .report-metadata span {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .test-card, .kpi-container {
            break-inside: avoid;
        }
    </style>
</head>
<body>

    <div class="endpoint-header">
        <h2><span class="method-badge">{{ http_method }}</span> {{ endpoint_path }}</h2>

        <div class="report-metadata">
            <span><strong>Comparativa:</strong> {{ reference_source }} ↔ {{ target_env }}</span>
            {% if execution_date != 'N/A' %}
            <span>📅 <strong>Fecha:</strong> {{ execution_date }}</span>
            <span>⏱️ <strong>Hora:</strong> {{ execution_time }} hs</span>
            {% endif %}
            {% if total_suite_duration %}
            <span>⚡ <strong>Duración Suite:</strong> {{ total_suite_duration }}</span>
            {% endif %}
        </div>
    </div>

    <div class="scope-note">
        Este reporte compara <b>PROD contra DEV en vivo</b>, caso por caso. No valida si el resultado es
        correcto según reglas de negocio — solo si ambos ambientes responden lo mismo. Para validación de
        reglas financieras contra el fixture congelado, ver el <i>Reporte de Regresión</i>.
    </div>

    <div class="kpi-container">
        <div class="kpi-card">
            <span>Casos Comparados</span>
            <div class="kpi-value">{{ total_scenarios }}</div>
        </div>
        <div class="kpi-card success">
            <span>Coincidencia entre Ambientes</span>
            <div class="kpi-value">{{ coincidence_percentage }}%</div>
        </div>
        <div class="kpi-card {% if failed_rules > 0 %}danger{% else %}success{% endif %}">
            <span>Con Diferencias</span>
            <div class="kpi-value">{{ failed_rules }} Caso(s)</div>
        </div>
        {% if avg_latency_delta_ms is defined %}
        <div class="kpi-card warning">
            <span>Δ Latencia Promedio (DEV − PROD)</span>
            <div class="kpi-value">{{ '+' if avg_latency_delta_ms >= 0 else '' }}{{ avg_latency_delta_ms }} ms</div>
        </div>
        {% endif %}
    </div>

    <h3>📋 Resultados por Caso Comparado</h3>

    <div class="filter-container">
        <button class="filter-btn active" onclick="filterResults(this, 'ALL')">Todos ({{ total_scenarios }})</button>
        <button class="filter-btn btn-passed" onclick="filterResults(this, 'PASSED')">Coinciden ({{ total_scenarios - failed_rules }})</button>
        <button class="filter-btn btn-failed" onclick="filterResults(this, 'FAILED')">Con Diferencias ({{ failed_rules }})</button>
    </div>

    <div id="test-results-list">
        {% for test in test_results %}
        <div class="test-card" data-status="{{ test.status }}">
            <div class="test-header">
                <h4>
                    <span class="badge {% if test.status == 'PASSED' %}bg-pass{% else %}bg-fail{% endif %}">{{ 'COINCIDE' if test.status == 'PASSED' else 'DIFERENCIA' }}</span>
                    {{ test.name }}
                </h4>

                {% if test.comparison_details %}
                <div class="env-time-group">
                    <span class="time-badge env-prod">PROD ⏱️ {{ test.comparison_details.prod_response.response_time_ms }} ms</span>
                    <span class="time-badge env-dev">DEV ⏱️ {{ test.comparison_details.dev_response.response_time_ms }} ms</span>
                </div>
                {% endif %}
            </div>

            <p>{{ test.description }}</p>

            {% if test.comparison_details %}
            <div class="env-compare-grid">
                <div class="env-col env-col-prod">
                    <div class="env-col-label"><span class="env-dot"></span>PROD</div>
                    <div class="env-status-line">HTTP <b>{{ test.comparison_details.prod_response.status_code }}</b> · fuente de referencia</div>
                </div>
                <div class="env-col env-col-dev">
                    <div class="env-col-label"><span class="env-dot"></span>DEV</div>
                    <div class="env-status-line">HTTP <b>{{ test.comparison_details.dev_response.status_code }}</b>{% if test.status == 'PASSED' %} · respuesta idéntica{% endif %}</div>
                </div>
            </div>

            {% if test.status == 'FAILED' and test.comparison_details.differences %}
            <div class="diff-list">
                <div class="diff-list-title">{{ test.comparison_details.differences | length }} diferencia(s) encontrada(s)</div>
                {% for diff in test.comparison_details.differences %}
                <div class="diff-row">
                    <span class="diff-path">{{ diff.path }}</span>
                    <span class="diff-value prod">{{ diff.prod_value if diff.prod_value is not none else 'falta en PROD' }}</span>
                    <span class="diff-arrow">→</span>
                    <span class="diff-value dev">{{ diff.dev_value if diff.dev_value is not none else 'falta en DEV' }}</span>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            {% elif test.status == 'FAILED' and test.error_log %}
            <pre>{{ test.error_log }}</pre>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <script>
        function filterResults(buttonElement, status) {
            const buttons = document.querySelectorAll('.filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            buttonElement.classList.add('active');

            const cards = document.querySelectorAll('.test-card');
            cards.forEach(card => {
                if (status === 'ALL') {
                    card.style.display = 'block';
                } else {
                    const cardStatus = card.getAttribute('data-status');
                    card.style.display = (cardStatus === status) ? 'block' : 'none';
                }
            });
        }

        window.onscroll = function() {
            const btn = document.getElementById("scrollToTopBtn");
            if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {
                btn.classList.add("show");
            } else {
                btn.classList.remove("show");
            }
        };

        function scrollToTop() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }
    </script>

    <button id="scrollToTopBtn" onclick="scrollToTop()" title="Volver arriba">▲</button>
</body>
</html>
"""


def _load_css_content() -> str:
    css_path = Path(__file__).parent / "report_styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def generate_execution_reports(
    data: dict,
    output_dir: str = "reports",
    report_prefix: str = "reporte_ejecucion",
    report_type: str = "regression",
    open_in_browser: bool = True
):
    """
    Genera los reportes HTML y PDF permitiendo definir el nombre base del archivo.

    :param data: Diccionario con los resultados y métricas.
    :param output_dir: Carpeta de destino (ej: reports/2026-08/17).
    :param report_prefix: Nombre base del archivo sin extensión (ej: 'reporte_comparacion_prod_vs_dev').
    :param report_type: 'regression' (contra fixture fijo) o 'comparison' (PROD vs DEV en vivo).
    :param open_in_browser: Si es True, abre el archivo HTML en el navegador al finalizar.
    """
    os.makedirs(output_dir, exist_ok=True)

    data["custom_css"] = _load_css_content()
    data.setdefault("execution_date", "N/A")
    data.setdefault("execution_time", "N/A")

    times = [t.get("response_time_ms") for t in data.get("test_results", []) if t.get("response_time_ms") is not None]
    if times and "avg_response_time" not in data:
        data["avg_response_time"] = round(sum(times) / len(times), 2)

    template_str = COMPARISON_TEMPLATE_HTML if report_type == "comparison" else REGRESSION_TEMPLATE_HTML
    template = Template(template_str)
    html_content = template.render(**data)

    # 🔹 Nomenclatura dinámica basada en report_prefix
    html_filename = f"{report_prefix}.html"
    pdf_filename = f"{report_prefix}.pdf"

    # 1. Guardar HTML
    html_path = os.path.abspath(os.path.join(output_dir, html_filename))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"-> Reporte HTML generado en: {html_path}")

    # 2. Generar PDF usando Playwright
    pdf_path = os.path.abspath(os.path.join(output_dir, pdf_filename))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"file:///{html_path}")
            page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=False,
                scale=0.9,
                margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"}
            )
            browser.close()
        print(f"-> Reporte PDF generado exitosamente en: {pdf_path}")
    except Exception as e:
        print(f"-> Error al generar el PDF con Playwright: {e}")

    # 3. Apertura automática en el navegador
    if open_in_browser:
        try:
            webbrowser.open(f"file:///{html_path}")
            print(f"-> Reporte '{html_filename}' abierto en el navegador predeterminado.")
        except Exception as e:
            print(f"-> No se pudo abrir el navegador automáticamente: {e}")
