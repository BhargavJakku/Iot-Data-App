import streamlit as st
from streamlit import errors
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
import os
from zoneinfo import ZoneInfo



# ---------- LOAD ENV VARIABLES ----------

if os.path.exists(".env"):
    load_dotenv()

def get_config(name: str, default: str | None = None):
    """
    Try to read from Streamlit secrets (Cloud / local secrets.toml).
    If no secrets file exists, gracefully fall back to environment variables.
    """
    # 1) Try secrets first
    try:
        return st.secrets[name]
    except errors.StreamlitSecretNotFoundError:
        return os.getenv(name, default)

#INFLUX_TOKEN = os.getenv("Influx_API_Token")
#INFLUX_TOKEN = st.secrets.get("INFLUX_TOKEN", os.getenv("Influx_API_Token"))


# 🟢 NEW: InfluxDB Configuration
INFLUX_URL = "https://us-east-1-1.aws.cloud2.influxdata.com" # e.g., "http://localhost:8086"
INFLUX_TOKEN = get_config("Influx_API_Token")
INFLUX_ORG = "PlantPet"
INFLUX_BUCKET = "PlantPet"
MEASUREMENT_NAME ="plant_status"  # Your measurement name

# --- CONFIGURATION CONSTANTS (UNCHANGED) ---
SOIL_WET = 700
SOIL_DRY = 2300
LIGHT_LOW = 450
LIGHT_HIGH = 3000
IDEAL_SOIL_MIN = 35 # %
IDEAL_SOIL_MAX = 75 # %


# ---------- PAGE CONFIG (UNCHANGED) ----------
st.set_page_config(
    page_title="Plant Health Dashboard",
    layout="wide",
)

# ---------- CUSTOM CSS (UNCHANGED) ----------
CUSTOM_CSS = """
<style>
/* App background */
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at top left, #1e293b 0, #020617 45%, #000 100%);
    color: #e5e7eb;
}

/* Sidebar Dark Mode */
[data-testid="stSidebar"] {
    background-color: #020617; 
    border-right: 1px solid rgba(148, 163, 184, 0.35);
}

/* Remove top white padding / header background */
[data-testid="stHeader"] {
    background: rgba(0,0,0,0);
}

/* Cards */
.card {
    background: rgba(15, 23, 42, 0.96);
    border-radius: 20px;
    padding: 1.3rem 1.5rem;
    border: 1px solid rgba(148, 163, 184, 0.35);
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(18px);
}

/* Titles */
.card-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #e5e7eb;
    margin-bottom: 0.35rem;
}

.card-caption {
    font-size: 0.78rem;
    color: #9ca3af;
    margin-bottom: 0.7rem;
}

/* Notification chip */
.notice-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.45rem 0.7rem;
    font-size: 0.75rem;
    border-radius: 999px;
    background: rgba(15,23,42,0.96);
    border: 1px solid rgba(148,163,184,0.6);
    box-shadow: 0 18px 40px rgba(15,23,42,0.9);
    margin-top: 0.6rem;
}

.notice-dot {
    width: 9px;
    height: 9px;
    border-radius: 999px;
}

.notice-label {
    color: #e5e7eb;
}

/* Dark theme for plotly charts */
.js-plotly-plot .plotly, .plot-container {
    background-color: rgba(0,0,0,0) !important;
}
/* Removes the pill section background */
h3 {
    padding: 0px 0px 10px 0px; 
    border-bottom: 1px solid rgba(148,163,184,0.2);
}

</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 🟢 NEW: Function to fetch data from InfluxDB
@st.cache_data(ttl=600)  # Cache for 10 minutes (matches your data update frequency)
def fetch_influxdb_data(days=7):
    """
    Fetch sensor data from InfluxDB for the last N days.
    Returns a DataFrame with columns: timestamp, soil_pct, light_pct, happiness
    """
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # 🟢 Flux query to fetch sensor data for last N days
        # Assumes your InfluxDB has fields: soil_pct, ldr_pct, happiness
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -{days}d)
            |> filter(fn: (r) => r["_measurement"] == "{MEASUREMENT_NAME}")
            |> filter(fn: (r) => r["_field"] == "soil_pct" or r["_field"] == "ldr_pct" or r["_field"] == "happiness")
            |> aggregateWindow(every: 10m, fn: mean, createEmpty: false)
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        # Execute query and convert to DataFrame
        result = query_api.query_data_frame(query)
        client.close()
        
        if result.empty:
            st.warning("No data found in InfluxDB for the specified time range.")
            return None
        
        # 🟢 Clean up the dataframe
        # Rename columns to match expected format
        LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Los_Angeles"))
        df = pd.DataFrame()
        utc_times = pd.to_datetime(result['_time'], utc=True)
        local_times = utc_times.dt.tz_convert(LOCAL_TZ)
        df['timestamp'] = local_times.dt.tz_localize(None)
        df['soil_pct'] = result.get('soil_pct', 0)
        df['light_pct'] = result.get('ldr_pct', 0)  # Note: using ldr_pct from InfluxDB
        df['happiness'] = result.get('happiness', 0)
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching data from InfluxDB: {str(e)}")
        return None

# 🟢 NEW: Load data function that uses InfluxDB
@st.cache_data(ttl=600)
def load_data():
    """
    Load real data from InfluxDB instead of generating dummy data
    """
    df = fetch_influxdb_data(days=7)
    
    if df is None or df.empty:
        # Fallback: create empty dataframe with expected structure
        st.error("Unable to load data from InfluxDB. Please check your connection settings.")
        return pd.DataFrame(columns=['timestamp', 'soil_pct', 'light_pct', 'happiness'])
    
    return df

# ---------- REUSABLE FUNCTIONS (UNCHANGED) ----------

def get_health_color(value: float):
    if value < 40:
        return "#ef4444"  # Red
    elif value < 70:
        return "#facc15"  # Yellow
    else:
        return "#22c55e"  # Green

def plot_sensor_data(df_filtered: pd.DataFrame, y_column: str, color: str, ideal_min: float = None, ideal_max: float = None, yaxis_title: str = None):
    # Function implementation remains the same
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered["timestamp"],
        y=df_filtered[y_column],
        mode="lines",
        line=dict(width=2, color=color)
    ))

    if ideal_min is not None and ideal_max is not None:
        fig.add_hrect(
            y0=ideal_min, y1=ideal_max,
            fillcolor="rgba(34, 197, 94, 0.15)",
            line_width=0,
            layer="below",
            annotation_text="Ideal Range",
            annotation_position="top left",
            annotation_font_color="#22c55e"
        )
        fig.add_hline(y=ideal_min, line=dict(dash='dash', width=1, color='rgba(34, 197, 94, 0.7)'), layer="below")
        fig.add_hline(y=ideal_max, line=dict(dash='dash', width=1, color='rgba(34, 197, 94, 0.7)'), layer="below")


    fig.update_layout(
        height=200,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(color="#9ca3af", showgrid=False, title=""),
        yaxis=dict(color="#9ca3af", showgrid=False, title=yaxis_title),
        hovermode="x unified",
    )
    return fig

# ---------- MAIN APP LAYOUT ----------
# 🟢 MODIFIED: Load real data from InfluxDB
df = load_data()

# 🟢 NEW: Safety check for empty dataframe
if df.empty:
    st.stop()

# --- SIDEBAR: Date Range Selection ---
now = datetime.now().date()
with st.sidebar:
    st.header("Date Range")
    # 🟢 MODIFIED: Use actual data date range
    min_date = df["timestamp"].min().date() if not df.empty else now - timedelta(days=7)
    max_date = df["timestamp"].max().date() if not df.empty else now
    
    start_date, end_date = st.date_input(
        "Select Historical Data Range",
        value=(max_date - timedelta(days=2), max_date),
        min_value=min_date,
        max_value=max_date
    )

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
df_filtered = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]

latest = df.iloc[-1]
latest_happiness = latest["happiness"]
latest_health_color = get_health_color(latest_happiness)

# --- HEADER ---
st.markdown("""<h1 style="text-align:center;margin-top:0;">  Plant Health Dashboard</h1>""", unsafe_allow_html=True)

# --- TOP SECTION: Plant Avatar (CENTERED IMPROVEMENT) ---

# Use the middle column for centering the content
col_top = st.columns([1, 1, 1])

with col_top[1]: 
    # The 'card' div is the key container. We will use it for centering.
    #st.markdown('<div class="card" style="text-align:center; padding: 2.5rem 1.5rem;">', unsafe_allow_html=True) 
    
    # 1. Title and Caption
    #st.markdown("<div class='card-title'>Live Plant Avatar</div>", unsafe_allow_html=True)
    #st.markdown("<div class='card-caption'>Glows based on real-time health.</div>", unsafe_allow_html=True)

    # 2. Dynamic glow Avatar (The margin:auto ensures centering)
    avatar_html = f"""
        <div style="
            width:180px;height:180px;border-radius:999px;
            margin: 15px auto; /* Centering and adding vertical space */
            background: radial-gradient(circle, {latest_health_color} 0%, rgba(6, 78, 59, 0.4) 70%);
            display:flex;align-items:center;justify-content:center;
            box-shadow:0px 0px 40px {latest_health_color};
        ">
            <span style="font-size:50px;">🌿</span>
        </div>
    """
    st.markdown(avatar_html, unsafe_allow_html=True)
    
    # 3. Happiness Score Value (Centered due to 'text-align:center' on parent card)
    score_html = f"""
        <div style="font-size: 38px; font-weight: 700; color: {latest_health_color}; margin-top: 15px; margin-bottom: 10px;text-align: center;">
            {int(latest_happiness)}%
        </div>
    """
    st.markdown(score_html, unsafe_allow_html=True)


    # 4. Dynamic status chip (Centered because it's an inline-flex element inside a centered block)
    if latest_happiness < 40:
        dot_color = "#ef4444"
        message = "ALERT • Critically low health! Check soil and light."
    elif latest_happiness < 70:
        dot_color = "#facc15"
        message = "WARNING • Health below optimal. Needs attention."
    else:
        dot_color = "#22c55e"
        message = "INFO • Conditions stable and optimal."

    # Use a surrounding div to center the inline-flex element itself
    chip_html = f"""
        <div style="text-align: center;">
            <div class="notice-chip">
                <div class="notice-dot" style="background:{dot_color}"></div>
                <div class="notice-label">{message}</div>
            </div>
        </div>
    """
    st.markdown(chip_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True) # Closing the card


# 🔴 MODIFIED: Changed from "24-Hour Trends" to "Last 7 Days Sensor Data"
st.markdown("<h3>Sensor Trends (Last 7 Days)</h3>", unsafe_allow_html=True)

# 🟢 MODIFIED: Show last 7 days instead of 24 hours
last_7_days = df[df["timestamp"] > df["timestamp"].max() - timedelta(days=7)]
col_soil, col_light = st.columns(2)


# SOIL SENSOR - 🟢 MODIFIED: Now showing 7 days of real data
with col_soil:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Soil Moisture (Last 7 Days)</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card-caption'>Current: **{latest['soil_pct']:.1f}%** (Target: {IDEAL_SOIL_MIN}% - {IDEAL_SOIL_MAX}%)</div>", unsafe_allow_html=True)
    st.markdown("<hr style='border:0;border-top:1px solid rgba(148,163,184,0.2);margin:8px 0 12px;'>", unsafe_allow_html=True)
    
    soil_fig = plot_sensor_data(last_7_days, "soil_pct", "#38bdf8", IDEAL_SOIL_MIN, IDEAL_SOIL_MAX, yaxis_title="Moisture (%)")
    st.plotly_chart(soil_fig, width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


# AMBIENT LIGHT - 🟢 MODIFIED: Now showing 7 days of real data
with col_light:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Ambient Light (Last 7 Days)</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card-caption'>Current: **{latest['light_pct']:.1f}%**</div>", unsafe_allow_html=True)
    st.markdown("<hr style='border:0;border-top:1px solid rgba(148,163,184,0.2);margin:8px 0 12px;'>", unsafe_allow_html=True)

    light_fig = plot_sensor_data(last_7_days, "light_pct", "#facc15", yaxis_title="Light (%)")
    st.plotly_chart(light_fig, width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


# 🔴 MODIFIED: Changed from "Correlation Analysis" to "Happiness Score with Soil & Light"
st.markdown("<h3>Happiness Score Analysis (Last 7 Days)</h3>", unsafe_allow_html=True)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("<div class='card-title'>Happiness Score with Soil Moisture & Ambient Light</div>", unsafe_allow_html=True)
st.markdown(f"<div class='card-caption'>Combined view of happiness score influenced by soil and light levels ({start_date} to {end_date}).</div>", unsafe_allow_html=True)

# 🟢 MODIFIED: Now includes happiness score in the chart
corr_df = df_filtered.set_index("timestamp")[["soil_pct", "light_pct", "happiness"]]

corr_fig = go.Figure()

# 🟢 NEW: Add happiness score trace
corr_fig.add_trace(go.Scatter(
    x=corr_df.index,
    y=corr_df["happiness"],
    mode="lines",
    name="Happiness (%)",
    line=dict(width=3, color="#22c55e"),
    yaxis="y1"
))

corr_fig.add_trace(go.Scatter(
    x=corr_df.index,
    y=corr_df["soil_pct"],
    mode="lines",
    name="Soil (%)",
    line=dict(width=2, color="#38bdf8", dash="dash"),
    yaxis="y1"
))

corr_fig.add_trace(go.Scatter(
    x=corr_df.index,
    y=corr_df["light_pct"],
    mode="lines",
    name="Light (%)",
    line=dict(width=2, color="#facc15", dash="dot"),
    yaxis="y1"
))

corr_fig.update_layout(
    height=350,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(color="#9ca3af", showgrid=True, gridcolor="rgba(148,163,184,0.1)", title="Percentage (%)", range=[0, 100]),
    xaxis=dict(color="#9ca3af", showgrid=False, title=""),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified"
)

st.plotly_chart(corr_fig, width="stretch")

st.markdown("</div>", unsafe_allow_html=True)