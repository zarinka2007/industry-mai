# app.py
import streamlit as st
import json
import folium
from folium.plugins import MarkerCluster
import streamlit.components.v1 as components
import random
from datetime import datetime
import math

# Page configuration
st.set_page_config(
    page_title="Наследие индустрии - Умный подбор локации",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Load regions data
@st.cache_data
def load_regions_data():
    with open('regions_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)


# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E5F8E;
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 3rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .region-card {
        background: white;
        border-radius: 15px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-size: 1.1rem;
        border-radius: 8px;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'input'
if 'selected_region' not in st.session_state:
    st.session_state.selected_region = None
if 'top3_regions' not in st.session_state:
    st.session_state.top3_regions = []
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}


# Calculation functions
def calculate_areas(volume, employees, housing_percent, kindergarten_places, insulation_type):
    """Calculate all required areas based on production parameters"""
    workshop = volume * 0.4  # тыс. м² панелей в год × 0.4 м²
    warehouse = workshop * 0.35
    abk = workshop * 0.02
    parking = employees * 0.5 * 25
    roads = (workshop + warehouse) * 0.25

    # Housing calculation
    if housing_percent > 0:
        housing_type_ratio = 25 if housing_percent <= 30 else 40  # общежитие / квартиры
        housing = employees * (housing_percent / 100) * housing_type_ratio
    else:
        housing = 0

    # Kindergarten
    kindergarten = (employees / 100) * kindergarten_places * 15 if kindergarten_places > 0 else 0

    # Social facilities
    canteen = employees * 0.5
    medical = max(20, employees * 0.1)

    total_area = workshop + warehouse + abk + parking + roads + housing + kindergarten + canteen + medical

    return {
        'workshop': round(workshop, 2),
        'warehouse': round(warehouse, 2),
        'abk': round(abk, 2),
        'parking': round(parking, 2),
        'roads': round(roads, 2),
        'housing': round(housing, 2),
        'kindergarten': round(kindergarten, 2),
        'canteen': round(canteen, 2),
        'medical': round(medical, 2),
        'total': round(total_area, 2)
    }


def calculate_budget(areas, sports_facilities, landscaping_count, insulation_type):
    """Calculate construction budget"""
    rates = {
        'workshop': 35000,
        'warehouse': 35000,
        'abk': 55000,
        'housing_dorm': 70000,
        'housing_apart': 90000,
        'kindergarten': 50000,
        'canteen': 35000,
        'medical': 45000,
        'roads': 5000,
        'landscaping': 2000
    }

    budget = 0
    budget += areas['workshop'] * rates['workshop']
    budget += areas['warehouse'] * rates['warehouse']
    budget += areas['abk'] * rates['abk']
    budget += areas['parking'] * rates['roads']
    budget += areas['roads'] * rates['roads']
    budget += areas['canteen'] * rates['canteen']
    budget += areas['medical'] * rates['medical']

    # Housing (assume 50/50 dorm/apartments for simplicity)
    if areas['housing'] > 0:
        budget += (areas['housing'] / 2) * rates['housing_dorm']
        budget += (areas['housing'] / 2) * rates['housing_apart']

    # Kindergarten
    if areas['kindergarten'] > 0:
        budget += areas['kindergarten'] * rates['kindergarten']

    # Landscaping
    budget += areas['total'] * rates['landscaping'] * landscaping_count

    # Sports facilities (one-time costs)
    sports_rates = {
        'Стадион': 5000000,
        'Бассейн': 8000000,
        'Спортзал': 3000000,
        'Хоккейная коробка': 2000000,
        'Уличные тренажёры': 500000
    }

    for facility in sports_facilities:
        budget += sports_rates.get(facility, 0)

    return round(budget, 2)


def calculate_region_score(region, form_data, areas):
    """Calculate region suitability score"""
    score = 0
    weights = {
        'logistics': 0.25,
        'economy': 0.25,
        'infrastructure': 0.20,
        'social': 0.15,
        'environment': 0.15
    }

    # Logistics score (steel and insulation proximity)
    min_steel_dist = min([s['distance'] for s in region['logistics']['steel_suppliers']])
    min_insulation_dist = min([s['distance'] for s in region['logistics']['insulation_suppliers']])
    logistics_score = max(0, 100 - (min_steel_dist / 10) - (min_insulation_dist / 15))

    # Economy score
    economy_score = 50
    if region['economy']['has_sez']:
        economy_score += 30
    if region['economy']['insurance_reduction']:
        economy_score += 10
    economy_score += min(10, (10 - region['economy']['energy_tariff']))

    # Infrastructure score
    infra_score = 50
    if region['infrastructure']['has_gas']:
        infra_score += 20
    if region['infrastructure']['free_power_kva'] >= 800:
        infra_score += 20
    else:
        infra_score += min(20, region['infrastructure']['free_power_kva'] / 40)
    if region['infrastructure']['railway_access'] and form_data.get('railway', False):
        infra_score += 10

    # Social score
    social_score = region['social']['environment_index'] * 10

    # Environment score
    env_score = max(0, (5 - region['environmental_class']) * 20) + 40

    # Weighted total
    total_score = (
            logistics_score * weights['logistics'] +
            economy_score * weights['economy'] +
            infra_score * weights['infrastructure'] +
            social_score * weights['social'] +
            env_score * weights['environment']
    )

    # Add some randomness for variety (±10%)
    random_factor = random.uniform(0.9, 1.1)
    total_score *= random_factor

    return round(total_score, 2)


def generate_concept_board(region, architecture_style):
    """Generate concept board based on region and style"""
    culture = region['culture']

    if architecture_style == "Аутентичность региону":
        primary_color = culture['color_palette']['primary']
        secondary_color = culture['color_palette']['secondary']
        accent_color = culture['color_palette']['accent']
        materials = culture['traditional_materials']
        style_desc = culture['architectural_style']
    elif architecture_style == "Техно-стиль":
        primary_color = "#2C3E50"
        secondary_color = "#34495E"
        accent_color = "#E74C3C"
        materials = ["Металл", "Стекло", "Бетон", "Композитные панели"]
        style_desc = "Современный индустриальный хай-тек"
    else:  # Экодизайн
        primary_color = "#27AE60"
        secondary_color = "#2ECC71"
        accent_color = "#F39C12"
        materials = ["Дерево", "Переработанные материалы", "Зеленые крыши", "Солнечные панели"]
        style_desc = "Экологичный устойчивый дизайн"

    return {
        'colors': {
            'primary': primary_color,
            'secondary': secondary_color,
            'accent': accent_color,
            'neutral': culture['color_palette']['neutral']
        },
        'materials': materials,
        'style': style_desc,
        'ornaments': culture['ornaments']
    }


def create_3d_visualization_html(areas, region, concept_board):
    """Generate Three.js 3D visualization HTML"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>3D Visualization</title>
        <style>
            body {{ margin: 0; overflow: hidden; }}
            #info {{
                position: absolute;
                top: 10px;
                left: 10px;
                background: rgba(255,255,255,0.9);
                padding: 10px;
                border-radius: 5px;
                font-family: Arial, sans-serif;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div id="info">
            <b>Производственный комплекс</b><br>
            Регион: {region['name']}<br>
            Общая площадь: {areas['total']} м²
        </div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
        <script>
            // Scene setup
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x87CEEB);

            const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
            camera.position.set(50, 40, 50);

            const renderer = new THREE.WebGLRenderer({{antialias: true}});
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            document.body.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;

            // Lights
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambientLight);

            const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
            dirLight.position.set(50, 100, 50);
            dirLight.castShadow = true;
            scene.add(dirLight);

            // Ground
            const groundGeometry = new THREE.PlaneGeometry(200, 200);
            const groundMaterial = new THREE.MeshLambertMaterial({{color: 0x7CFC00}});
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.receiveShadow = true;
            scene.add(ground);

            // Workshop (main building)
            const workshopGeo = new THREE.BoxGeometry({areas['workshop'] / 10}, 10, {areas['workshop'] / 15});
            const workshopMat = new THREE.MeshLambertMaterial({{color: '{concept_board['colors']['primary']}'}});
            const workshop = new THREE.Mesh(workshopGeo, workshopMat);
            workshop.position.set(0, 5, 0);
            workshop.castShadow = true;
            workshop.receiveShadow = true;
            scene.add(workshop);

            // Warehouse
            const warehouseGeo = new THREE.BoxGeometry({areas['warehouse'] / 10}, 8, {areas['warehouse'] / 15});
            const warehouseMat = new THREE.MeshLambertMaterial({{color: '{concept_board['colors']['secondary']}'}});
            const warehouse = new THREE.Mesh(warehouseGeo, warehouseMat);
            warehouse.position.set(-20, 4, 10);
            warehouse.castShadow = true;
            scene.add(warehouse);

            // ABK (office building)
            const abkGeo = new THREE.BoxGeometry(8, 6, 6);
            const abkMat = new THREE.MeshLambertMaterial({{color: '{concept_board['colors']['accent']}'}});
            const abk = new THREE.Mesh(abkGeo, abkMat);
            abk.position.set(15, 3, -10);
            abk.castShadow = true;
            scene.add(abk);

            // Animation
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }}
            animate();

            // Handle resize
            window.addEventListener('resize', () => {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
        </script>
    </body>
    </html>
    """
    return html


def create_map(top3_regions):
    """Create folium map with TOP-3 regions"""
    m = folium.Map(location=[55.7558, 37.6173], zoom_start=5, tiles='cartodbpositron')

    marker_cluster = MarkerCluster().add_to(m)

    colors = ['red', 'blue', 'green']

    for idx, region_data in enumerate(top3_regions):
        region = region_data['region']
        coords = region['coordinates']

        popup_html = f"""
        <div style="font-family: Arial; min-width: 200px;">
            <h4 style="margin: 0 0 10px 0; color: {colors[idx]};">{region['name']}</h4>
            <b>Рейтинг:</b> {region_data['score']}<br>
            <b>Стоимость подключения:</b> {region['infrastructure']['connection_cost_per_kw']} руб/кВт<br>
            <b>Энерготариф:</b> {region['economy']['energy_tariff']} руб/кВт·ч<br>
            <b>ОЭЗ/ТОР:</b> {'✓ ' + region['economy']['sez_name'] if region['economy']['has_sez'] else '✗ Нет'}<br>
            <b>Свободная мощность:</b> {region['infrastructure']['free_power_kva']} кВА
        </div>
        """

        folium.Marker(
            location=[coords['lat'], coords['lon']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=colors[idx], icon='industry', prefix='fa'),
            tooltip=f"{idx + 1}. {region['name']} - {region_data['score']}"
        ).add_to(marker_cluster)

    return m


def generate_analytical_report(region, form_data, areas, budget, concept_board):
    """Generate comprehensive analytical report"""
    report = {
        'social_passport': {
            'region_name': region['name'],
            'environment_index': region['social']['environment_index'],
            'kindergartens_availability': f"{region['social']['kindergartens_per_100']} мест на 100 детей",
            'vocational_schools': region['social']['vocational_colleges'],
            'avg_rent': f"{region['social']['avg_rent_1room']:,} руб/мес",
            'avg_salary': f"{region['social']['avg_salary']:,} руб/мес",
            'population': f"{region['social']['population']:,} человек"
        },
        'economy': {
            'sez_available': region['economy']['has_sez'],
            'sez_name': region['economy']['sez_name'],
            'tax_rate': f"{region['economy']['tax_benefit_percent']}%" if region['economy'][
                'has_sez'] else "Стандартная",
            'insurance_reduction': "✓ 7.6%" if region['economy']['insurance_reduction'] else "✗ 30%",
            'energy_tariff': f"{region['economy']['energy_tariff']} руб/кВт·ч",
            'grpp_per_capita': f"{region['economy']['grpp_per_capita']:,} руб",
            'industrial_growth': f"{region['economy']['industrial_growth']}%"
        },
        'infrastructure': {
            'gas_available': "✓ Есть" if region['infrastructure']['has_gas'] else "✗ Нет",
            'free_power': f"{region['infrastructure']['free_power_kva']} кВА",
            'distance_to_substation': f"{region['infrastructure']['distance_to_substation']} км",
            'connection_cost': f"{region['infrastructure']['connection_cost_per_kw']} руб/кВт",
            'railway': "✓ Есть" if region['infrastructure']['railway_access'] else "✗ Нет",
            'highway': "✓ Есть" if region['infrastructure']['highway_access'] else "✗ Нет"
        },
        'logistics': {
            'steel_suppliers': region['logistics']['steel_suppliers'],
            'insulation_suppliers': region['logistics']['insulation_suppliers'],
            'sales_radius': f"{region['logistics']['sales_radius']} км"
        },
        'staff_retention': {
            'housing_needed': f"{form_data['housing_percent']}% сотрудников",
            'kindergarten_places': f"{form_data['kindergarten_places']} мест на 100 сотрудников",
            'transport_recommendation': "Рекомендуется корпоративный транспорт" if form_data[
                                                                                       'max_distance'] > 15 else "Доступность удовлетворительная",
            'sports_facilities': form_data['sports']
        },
        'budget': {
            'total_construction': f"{budget:,.2f} руб",
            'areas': areas,
            'within_budget': budget <= form_data['budget'] * 1e6
        },
        'concept': concept_board
    }

    return report


# Main app
def main():
    # Header
    st.markdown('<h1 class="main-header">🏭 Наследие индустрии</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Умный подбор локации и дизайна для производства с местным характером</p>',
                unsafe_allow_html=True)

    # Sidebar for navigation
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2830/2830308.png", width=100)
        st.title("Навигация")

        if st.session_state.page == 'input':
            if st.button("📊 Результаты", use_container_width=True):
                st.session_state.page = 'results'
                st.rerun()
        else:
            if st.button("⬅️ Вернуться к форме", use_container_width=True):
                st.session_state.page = 'input'
                st.rerun()

        st.markdown("---")
        st.info("💡 Заполните форму для подбора оптимальной локации")

    if st.session_state.page == 'input':
        render_input_page()
    else:
        render_results_page()


def render_input_page():
    """Render the input form page"""
    regions_data = load_regions_data()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📋 Параметры производства")

        with st.form("production_form"):
            # Production parameters
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                volume = st.slider(
                    "Объем выпуска (тыс. м²/год)",
                    min_value=100,
                    max_value=1000,
                    value=300,
                    step=50,
                    help="Годовой объем производства сэндвич-панелей"
                )

            with col_b:
                employees = st.slider(
                    "Количество сотрудников",
                    min_value=10,
                    max_value=200,
                    value=50,
                    step=10
                )

            with col_c:
                budget = st.slider(
                    "Бюджет (млн руб)",
                    min_value=10,
                    max_value=300,
                    value=100,
                    step=10
                )

            st.markdown("### 🚚 Логистика")
            col_d, col_e = st.columns(2)

            with col_d:
                railway = st.selectbox(
                    "Необходима ж/д ветка",
                    options=["Да", "Нет"],
                    index=0
                )

            with col_e:
                max_distance = st.slider(
                    "Макс. расстояние до федеральной трассы (км)",
                    min_value=1,
                    max_value=100,
                    value=30,
                    step=5
                )

            st.markdown("### 🏛️ Архитектура и стиль")
            col_f, col_g = st.columns(2)

            with col_f:
                architecture_style = st.selectbox(
                    "Архитектурный приоритет",
                    options=["Аутентичность региону", "Техно-стиль", "Экодизайн"],
                    index=0
                )

            with col_g:
                landscaping = st.multiselect(
                    "Благоустройство (до 3)",
                    options=["Аллея", "Сквер с фонтаном", "Беседки", "Сцена",
                             "Тропа здоровья", "Пруд", "Арт-объект"],
                    default=["Аллея"]
                )

            st.markdown("### 👥 Социальные приоритеты")
            col_h, col_i, col_j = st.columns(3)

            with col_h:
                housing_percent = st.selectbox(
                    "Обеспечение жильём",
                    options=["0%", "30%", "50%", "70%"],
                    index=1
                )

            with col_i:
                kindergarten_places = st.selectbox(
                    "Детский сад (мест на 100 сотр.)",
                    options=[0, 15, 30, 50],
                    index=1
                )

            with col_j:
                sports = st.multiselect(
                    "Спорт (до 2)",
                    options=["Уличные тренажёры", "Стадион", "Бассейн",
                             "Спортзал", "Хоккейная коробка"],
                    default=["Уличные тренажёры"]
                )

            submitted = st.form_submit_button("🔍 Найти участок", use_container_width=True)

            if submitted:
                # Process form data
                st.session_state.form_data = {
                    'volume': volume,
                    'employees': employees,
                    'budget': budget,
                    'railway': railway == "Да",
                    'max_distance': max_distance,
                    'architecture_style': architecture_style,
                    'landscaping': landscaping,
                    'housing_percent': int(housing_percent.replace('%', '')),
                    'kindergarten_places': kindergarten_places,
                    'sports': sports
                }

                # Calculate areas and budget
                areas = calculate_areas(
                    volume, employees,
                    int(housing_percent.replace('%', '')),
                    kindergarten_places,
                    "ППУ"  # Default insulation type
                )

                budget_calc = calculate_budget(
                    areas, sports,
                    len(landscaping),
                    "ППУ"
                )

                # Calculate scores for all regions and select TOP-3
                regions_with_scores = []
                for region in regions_data['regions']:
                    score = calculate_region_score(region, st.session_state.form_data, areas)
                    regions_with_scores.append({
                        'region': region,
                        'score': score
                    })

                # Sort by score and take TOP-3
                regions_with_scores.sort(key=lambda x: x['score'], reverse=True)
                st.session_state.top3_regions = regions_with_scores[:3]

                # Generate concept boards for each region
                for region_data in st.session_state.top3_regions:
                    region_data['concept_board'] = generate_concept_board(
                        region_data['region'],
                        architecture_style
                    )
                    region_data['areas'] = areas
                    region_data['budget'] = budget_calc

                st.session_state.page = 'results'
                st.rerun()

    with col2:
        st.markdown("### 💡 Рекомендации")
        st.info("""
        **Для оптимального подбора:**

        1. Учитывайте логистику сырья
        2. Обращайте внимание на наличие ОЭЗ
        3. Проверяйте доступность сетей
        4. Планируйте социальную инфраструктуру
        """)

        st.markdown("### 📊 Пример расчета")
        st.success("""
        При объеме 300 тыс. м²/год:
        - Цех: 120 м²
        - Склад: 42 м²
        - АБК: 2.4 м²
        """)


def render_results_page():
    """Render the results page with TOP-3 regions"""
    if not st.session_state.top3_regions:
        st.warning("Сначала заполните форму для получения результатов")
        st.session_state.page = 'input'
        st.rerun()

    form_data = st.session_state.form_data
    top3 = st.session_state.top3_regions

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📍 Карта и регионы", "📊 Детальная аналитика", "🎨 Концепт-борды", "📑 Презентация"])

    with tab1:
        st.markdown("### 🗺️ ТОП-3 региона на карте")

        # Create and display map
        map_html = create_map(top3).get_root().render()
        components.html(map_html, height=500, scrolling=False)

        st.markdown("### 🏆 Рейтинг регионов")

        for idx, region_data in enumerate(top3, 1):
            region = region_data['region']
            score = region_data['score']

            with st.expander(
                    f"{'🥇' if idx == 1 else '🥈' if idx == 2 else '🥉'} {idx}. {region['name']} - Рейтинг: {score}",
                    expanded=(idx == 1)):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**📍 Основная информация**")
                    st.write(f"Столица: {region['capital']}")
                    st.write(f"Федеральный округ: {region['federal_district']}")
                    st.write(f"Население: {region['social']['population']:,} чел.")

                with col2:
                    st.markdown("**💰 Экономика**")
                    if region['economy']['has_sez']:
                        st.success(f"✓ ОЭЗ: {region['economy']['sez_name']}")
                        st.write(f"Налог на прибыль: {region['economy']['tax_benefit_percent']}%")
                    else:
                        st.warning("✗ ОЭЗ отсутствует")
                    st.write(f"Энерготариф: {region['economy']['energy_tariff']} руб/кВт·ч")

                st.markdown("**🔌 Инфраструктура**")
                col3, col4 = st.columns(2)
                with col3:
                    st.write(f"Газ: {'✓' if region['infrastructure']['has_gas'] else '✗'}")
                    st.write(f"Ж/д: {'✓' if region['infrastructure']['railway_access'] else '✗'}")
                with col4:
                    st.write(f"Свободная мощность: {region['infrastructure']['free_power_kva']} кВА")
                    st.write(f"Стоимость подключения: {region['infrastructure']['connection_cost_per_kw']} руб/кВт")

                st.markdown("**📦 Логистика**")
                st.write(
                    f"Ближайший поставщик стали: {region['logistics']['steel_suppliers'][0]['name']} ({region['logistics']['steel_suppliers'][0]['distance']} км)")
                st.write(
                    f"Ближайший поставщик утеплителя: {region['logistics']['insulation_suppliers'][0]['name']} ({region['logistics']['insulation_suppliers'][0]['distance']} км)")

    with tab2:
        st.markdown("### 📊 Детальная аналитика")

        # Region selector
        selected_idx = st.selectbox(
            "Выберите регион для детального анализа",
            options=[f"{i + 1}. {r['region']['name']}" for i, r in enumerate(top3)],
            index=0
        )
        selected_region_data = top3[int(selected_idx.split('.')[0]) - 1]
        selected_region = selected_region_data['region']

        # Generate full report
        report = generate_analytical_report(
            selected_region,
            form_data,
            selected_region_data['areas'],
            selected_region_data['budget'],
            selected_region_data['concept_board']
        )

        # Social passport
        st.markdown("### 👥 Социальный паспорт региона")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Индекс качества среды", f"{report['social_passport']['environment_index']}/10")
            st.metric("Детские сады", report['social_passport']['kindergartens_availability'])
        with col2:
            st.metric("Проф. училища", report['social_passport']['vocational_schools'])
            st.metric("Средняя аренда", report['social_passport']['avg_rent'])
        with col3:
            st.metric("Средняя зарплата", report['social_passport']['avg_salary'])
            st.metric("Население", report['social_passport']['population'])

        # Economy
        st.markdown("### 💵 Экономика и льготы")
        col4, col5, col6 = st.columns(3)
        with col4:
            st.info(
                f"ОЭЗ: {'✓ ' + selected_region['economy']['sez_name'] if selected_region['economy']['has_sez'] else '✗ Нет'}")
        with col5:
            st.info(f"Налог: {report['economy']['tax_rate']}")
            st.info(f"Страховые: {report['economy']['insurance_reduction']}")
        with col6:
            st.info(f"Энерготариф: {report['economy']['energy_tariff']}")
            st.info(f"Рост пром.: {report['economy']['industrial_growth']}")

        # Infrastructure
        st.markdown("### 🔌 Сетевая инфраструктура")
        col7, col8 = st.columns(2)
        with col7:
            st.write(f"**Газ:** {report['infrastructure']['gas_available']}")
            st.write(f"**Ж/д:** {report['infrastructure']['railway']}")
            st.write(f"**Трасса:** {report['infrastructure']['highway']}")
        with col8:
            st.write(f"**Свободная мощность:** {report['infrastructure']['free_power']}")
            st.write(f"**Подключение:** {report['infrastructure']['connection_cost']}")
            st.write(f"**Расстояние до ПС:** {report['infrastructure']['distance_to_substation']}")

        # Budget
        st.markdown("### 💰 Предварительная смета")
        areas = selected_region_data['areas']
        budget = selected_region_data['budget']

        col9, col10 = st.columns(2)
        with col9:
            st.write("**Площади объектов:**")
            st.write(f"• Цех: {areas['workshop']} м²")
            st.write(f"• Склад: {areas['warehouse']} м²")
            st.write(f"• АБК: {areas['abk']} м²")
            st.write(f"• Парковка: {areas['parking']} м²")
            if areas['housing'] > 0:
                st.write(f"• Жильё: {areas['housing']} м²")
            if areas['kindergarten'] > 0:
                st.write(f"• Детский сад: {areas['kindergarten']} м²")

        with col10:
            st.write("**Стоимость:**")
            st.metric("Общий бюджет", f"{budget:,.0f} руб")
            if budget <= form_data['budget'] * 1e6:
                st.success("✓ Вписывается в бюджет")
            else:
                st.error("✗ Превышает бюджет")

    with tab3:
        st.markdown("### 🎨 Концепт-борды")

        # Show all 3 concept boards
        for idx, region_data in enumerate(top3, 1):
            st.markdown(f"#### {'🥇' if idx == 1 else '🥈' if idx == 2 else '🥉'} {region_data['region']['name']}")

            concept = region_data['concept_board']

            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown("**Цветовая палитра**")
                colors_html = f"""
                <div style="display: flex; height: 100px; border-radius: 10px; overflow: hidden;">
                    <div style="flex: 1; background: {concept['colors']['primary']}; display: flex; align-items: flex-end; justify-content: center; color: white; padding: 5px; font-size: 12px;">Основной</div>
                    <div style="flex: 1; background: {concept['colors']['secondary']}; display: flex; align-items: flex-end; justify-content: center; color: white; padding: 5px; font-size: 12px;">Вторичный</div>
                    <div style="flex: 1; background: {concept['colors']['accent']}; display: flex; align-items: flex-end; justify-content: center; color: white; padding: 5px; font-size: 12px;">Акцент</div>
                    <div style="flex: 1; background: {concept['colors']['neutral']}; display: flex; align-items: flex-end; justify-content: center; color: black; padding: 5px; font-size: 12px;">Нейтральный</div>
                </div>
                """
                st.markdown(colors_html, unsafe_allow_html=True)

                st.markdown("**Материалы**")
                for material in concept['materials']:
                    st.write(f"• {material}")

                st.markdown("**Орнаменты**")
                for ornament in concept['ornaments']:
                    st.write(f"• {ornament}")

            with col2:
                st.markdown("**Стиль**")
                st.info(concept['style'])

                # Generate placeholder for renders (in real app, this would be AI-generated)
                st.markdown("**Пример визуализации**")
                st.image(
                    "https://images.unsplash.com/photo-1565008447742-914f288056a1?w=800",
                    caption="Концепт промышленного объекта",
                    width="stretch"
                )

            st.markdown("---")

        # 3D Visualization
        st.markdown("### 🏗️ Интерактивная 3D-визуализация")
        selected_for_3d = st.selectbox(
            "Выберите регион для 3D визуализации",
            options=[f"{i + 1}. {r['region']['name']}" for i, r in enumerate(top3)]
        )
        region_3d_data = top3[int(selected_for_3d.split('.')[0]) - 1]

        html_3d = create_3d_visualization_html(
            region_3d_data['areas'],
            region_3d_data['region'],
            region_3d_data['concept_board']
        )

        components.html(html_3d, height=600, scrolling=False)

    with tab4:
        st.markdown("### 📑 Презентация для администрации")

        selected_presentation = st.selectbox(
            "Выберите регион",
            options=[f"{i + 1}. {r['region']['name']}" for i, r in enumerate(top3)]
        )
        pres_region_data = top3[int(selected_presentation.split('.')[0]) - 1]
        pres_region = pres_region_data['region']

        # Slide 1: Title
        st.markdown("---")
        st.markdown(f"""
        <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;">
            <h1>Проект строительства производства сэндвич-панелей</h1>
            <h2>{pres_region['name']}</h2>
            <p>Инвестиционный проект с созданием {form_data['employees']} рабочих мест</p>
        </div>
        """, unsafe_allow_html=True)

        # Slide 2: Parameters
        st.markdown("---")
        st.markdown("### Параметры проекта")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Производство:** {form_data['volume']} тыс. м²/год")
            st.write(f"**Рабочие места:** {form_data['employees']}")
            st.write(f"**Инвестиции:** {form_data['budget']} млн руб")
        with col2:
            st.write(f"**Жильё:** {form_data['housing_percent']}% сотрудников")
            st.write(f"**Детский сад:** {form_data['kindergarten_places']} мест/100 сотр.")
            st.write(f"**Спорт:** {', '.join(form_data['sports'])}")

        # Slide 3: Renders (placeholders)
        st.markdown("---")
        st.markdown("### Визуализация объекта (4 ракурса)")
        col1, col2 = st.columns(2)
        with col1:
            st.image("https://images.unsplash.com/photo-1565008447742-914f288056a1?w=400", caption="Вид с юга")
            st.image("https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=400", caption="Вид с запада")
        with col2:
            st.image("https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=400", caption="Вид с севера")
            st.image("https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400", caption="Вид с востока")

        # Slide 4: Site plan
        st.markdown("---")
        st.markdown("### План участка")
        areas = pres_region_data['areas']
        st.write(f"**Общая площадь:** {areas['total']} м²")
        st.write(f"• Производственный цех: {areas['workshop']} м²")
        st.write(f"• Склад: {areas['warehouse']} м²")
        st.write(f"• АБК: {areas['abk']} м²")
        if areas['housing'] > 0:
            st.write(f"• Жильё для сотрудников: {areas['housing']} м²")
        if areas['kindergarten'] > 0:
            st.write(f"• Детский сад: {areas['kindergarten']} м²")

        # Slide 5: Compliance
        st.markdown("---")
        st.markdown("### Соответствие требованиям")
        col3, col4 = st.columns(2)
        with col3:
            st.success("✓ Доступность газа" if pres_region['infrastructure']['has_gas'] else "⚠️ Газ отсутствует")
            st.success(
                f"✓ Мощность {pres_region['infrastructure']['free_power_kva']} кВА" if pres_region['infrastructure'][
                                                                                           'free_power_kva'] >= 300 else "⚠️ Требуется увеличение мощности")
        with col4:
            st.success("✓ Ж/д ветка" if pres_region['infrastructure']['railway_access'] else "⚠️ Ж/д отсутствует")
            st.success("✓ Федеральная трасса" if pres_region['infrastructure'][
                'highway_access'] else "⚠️ Удалённость от трассы")

        # Slide 6: Economics
        st.markdown("---")
        st.markdown("### Экономика и социальные выгоды")
        col5, col6 = st.columns(2)
        with col5:
            st.write("**Для региона:**")
            st.write(f"• Налоговые поступления")
            st.write(f"• {form_data['employees']} рабочих мест")
            if pres_region['economy']['has_sez']:
                st.write(f"• Статус резидента ОЭЗ \"{pres_region['economy']['sez_name']}\"")
            st.write(f"• Развитие инфраструктуры")
        with col6:
            st.write("**Для инвестора:**")
            if pres_region['economy']['has_sez']:
                st.write(f"• Налог на прибыль: {pres_region['economy']['tax_benefit_percent']}%")
            if pres_region['economy']['insurance_reduction']:
                st.write("• Страховые взносы: 7.6%")
            st.write(f"• Энерготариф: {pres_region['economy']['energy_tariff']} руб/кВт·ч")
            st.write("• Готовая инфраструктура")

        st.markdown("---")

        # Download button for presentation
        # Генерация и скачивание презентации
        pres_region_data = top3[int(selected_presentation.split('.')[0]) - 1]
        pres_region = pres_region_data['region']

        # Получаем данные для презентации
        p_areas = pres_region_data['areas']
        p_budget = pres_region_data['budget']
        p_concept = pres_region_data['concept_board']

        # Генерируем HTML
        presentation_html = generate_presentation_html(pres_region_data, form_data, p_areas, p_budget, p_concept)

        st.download_button(
            label="📥 Скачать презентацию (HTML)",
            data=presentation_html,
            file_name=f"Presentation_{pres_region['name'].replace(' ', '_')}.html",
            mime="text/html"
        )

        st.info("💡 Скачайте файл и откройте его в любом браузере (Chrome, Edge). Это готовая презентация из 6 слайдов.")

def generate_presentation_html(region_data, form_data, areas, budget, concept_board):
    """Генерирует HTML-файл презентации из 6 слайдов"""
    region = region_data['region']

    # Определяем цвета для слайдов
    primary_color = concept_board['colors']['primary']

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Презентация проекта: {region['name']}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f0f2f6; }}
            .slide {{ 
                width: 100%; 
                height: 100vh; 
                display: flex; 
                flex-direction: column; 
                justify-content: center; 
                align-items: center; 
                page-break-after: always; 
                background: white; 
                padding: 40px; 
                box-sizing: border-box;
                border-bottom: 5px solid {primary_color};
            }}
            .slide h1 {{ color: {primary_color}; font-size: 3em; margin-bottom: 20px; text-align: center; }}
            .slide h2 {{ color: #333; font-size: 2em; margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 10px; width: 100%; }}
            .content {{ width: 80%; font-size: 1.2em; line-height: 1.6; color: #444; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; width: 100%; }}
            .card {{ background: #f9f9f9; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .metric {{ font-size: 1.5em; font-weight: bold; color: {primary_color}; }}
            .footer {{ position: fixed; bottom: 10px; right: 20px; font-size: 0.8em; color: #999; }}
            img {{ max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ margin-bottom: 10px; padding-left: 20px; position: relative; }}
            li::before {{ content: "✓"; color: {primary_color}; position: absolute; left: 0; font-weight: bold; }}
        </style>
    </head>
    <body>
        <!-- Слайд 1: Титул -->
        <div class="slide">
            <h1>Наследие индустрии</h1>
            <h2>Проект производства сэндвич-панелей</h2>
            <div class="content" style="text-align: center;">
                <p style="font-size: 1.5em;"><b>Регион:</b> {region['name']}</p>
                <p><b>Инвестор:</b> Команда разработчиков</p>
                <p><b>Дата:</b> 2026 г.</p>
            </div>
        </div>

        <!-- Слайд 2: Параметры проекта -->
        <div class="slide">
            <h2>Параметры проекта</h2>
            <div class="content">
                <div class="grid">
                    <div class="card">
                        <h3>Производство</h3>
                        <p>Объем выпуска: <span class="metric">{form_data['volume']} тыс. м²/год</span></p>
                        <p>Сотрудников: <span class="metric">{form_data['employees']} чел.</span></p>
                        <p>Бюджет: <span class="metric">{form_data['budget']} млн руб.</span></p>
                    </div>
                    <div class="card">
                        <h3>Социальный пакет</h3>
                        <ul>
                            <li>Жилье: {form_data['housing_percent']}% сотрудников</li>
                            <li>Детский сад: {form_data['kindergarten_places']} мест</li>
                            <li>Спорт: {', '.join(form_data['sports'])}</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <!-- Слайд 3: Визуализация (Рендеры) -->
        <div class="slide">
            <h2>Архитектурный концепт</h2>
            <div class="content">
                <p>Стиль: {concept_board['style']}</p>
                <div class="grid">
                    <div class="card" style="text-align:center;">
                        <img src="https://images.unsplash.com/photo-1565008447742-914f288056a1?w=400" alt="Вид с юга">
                        <p>Вид с юга</p>
                    </div>
                    <div class="card" style="text-align:center;">
                        <img src="https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=400" alt="Вид с запада">
                        <p>Вид с запада</p>
                    </div>
                </div>
                <div class="grid" style="margin-top: 20px;">
                    <div class="card" style="text-align:center;">
                        <img src="https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=400" alt="Вид с севера">
                        <p>Вид с севера</p>
                    </div>
                    <div class="card" style="text-align:center;">
                        <img src="https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400" alt="Вид с востока">
                        <p>Вид с востока</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Слайд 4: План участка -->
        <div class="slide">
            <h2>План участка и застройка</h2>
            <div class="content">
                <p>Общая площадь застройки: <span class="metric">{areas['total']} м²</span></p>
                <div class="grid">
                    <div class="card">
                        <h3>Производственный блок</h3>
                        <ul>
                            <li>Цех: {areas['workshop']} м²</li>
                            <li>Склад: {areas['warehouse']} м²</li>
                            <li>АБК: {areas['abk']} м²</li>
                        </ul>
                    </div>
                    <div class="card">
                        <h3>Социальный блок</h3>
                        <ul>
                            <li>Парковка: {areas['parking']} м²</li>
                            {'<li>Жилье: ' + str(areas['housing']) + ' м²</li>' if areas['housing'] > 0 else ''}
                            {'<li>Детский сад: ' + str(areas['kindergarten']) + ' м²</li>' if areas['kindergarten'] > 0 else ''}
                            <li>Столовая и медпункт</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <!-- Слайд 5: Инфраструктура и сети -->
        <div class="slide">
            <h2>Инфраструктура и соответствие нормам</h2>
            <div class="content">
                <div class="grid">
                    <div class="card">
                        <h3>Сети и коммуникации</h3>
                        <ul>
                            <li>Газ: {'Есть' if region['infrastructure']['has_gas'] else 'Нет'}</li>
                            <li>Электричество: {region['infrastructure']['free_power_kva']} кВА свободно</li>
                            <li>Подключение: {region['infrastructure']['connection_cost_per_kw']} руб/кВт</li>
                            <li>Ж/д ветка: {'Есть' if region['infrastructure']['railway_access'] else 'Нет'}</li>
                        </ul>
                    </div>
                    <div class="card">
                        <h3>Логистика</h3>
                        <ul>
                            <li>Сталь: {region['logistics']['steel_suppliers'][0]['distance']} км</li>
                            <li>Утеплитель: {region['logistics']['insulation_suppliers'][0]['distance']} км</li>
                            <li>Радиус сбыта: {region['logistics']['sales_radius']} км</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <!-- Слайд 6: Экономика и выгоды -->
        <div class="slide">
            <h2>Экономика и социальный эффект</h2>
            <div class="content">
                <div class="grid">
                    <div class="card">
                        <h3>Для инвестора</h3>
                        <p>Смета строительства: <span class="metric">{budget:,.0f} руб.</span></p>
                        <ul>
                            <li>Налог на прибыль: {region['economy']['tax_benefit_percent']}% (ОЭЗ)</li>
                            <li>Страховые взносы: {'7.6%' if region['economy']['insurance_reduction'] else '30%'}</li>
                            <li>Энерготариф: {region['economy']['energy_tariff']} руб/кВт·ч</li>
                        </ul>
                    </div>
                    <div class="card">
                        <h3>Для региона</h3>
                        <ul>
                            <li>{form_data['employees']} новых рабочих мест</li>
                            <li>Налоговые отчисления в бюджет</li>
                            <li>Развитие социальной инфраструктуры</li>
                            <li>Использование местных материалов</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">Сгенерировано системой "Наследие индустрии"</div>
    </body>
    </html>
    """
    return html_content

if __name__ == "__main__":
    main()