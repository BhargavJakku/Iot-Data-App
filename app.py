import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

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

# ---------- DATA GENERATION (UNCHANGED) ----------
@st.cache_data
def load_data():
    now = datetime.now()
    times = pd.date_range(end=now, periods=7 * 24, freq="H")

    soil_raw = np.random.randint(SOIL_WET, SOIL_DRY, size=len(times))
    light_raw = np.random.randint(LIGHT_LOW, LIGHT_HIGH, size=len(times))

    df = pd.DataFrame(
        {
            "timestamp": times,
            "soil_raw": soil_raw,
            "light_raw": light_raw,
        }
    )

    df["soil_pct"] = (SOIL_DRY - df["soil_raw"]) / (SOIL_DRY - SOIL_WET) * 100
    df["soil_pct"] = df["soil_pct"].clip(0, 100)

    df["light_pct"] = (df["light_raw"] - LIGHT_LOW) / (LIGHT_HIGH - LIGHT_LOW) * 100
    df["light_pct"] = df["light_pct"].clip(0, 100)

    # Simplified happiness score calculation
    soil_score = np.where(
        (df["soil_pct"] >= IDEAL_SOIL_MIN) & (df["soil_pct"] <= IDEAL_SOIL_MAX),
        100,
        (1 - np.abs(df["soil_pct"] - (IDEAL_SOIL_MIN + IDEAL_SOIL_MAX) / 2) / ((IDEAL_SOIL_MAX - IDEAL_SOIL_MIN) / 2)) * 100
    ).clip(0, 100)

    light_score = df["light_pct"]

    df["happiness"] = (
        0.6 * soil_score + 
        0.4 * light_score
    )

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
df = load_data()

# --- SIDEBAR: Date Range Selection ---
now = datetime.now().date()
with st.sidebar:
    st.header("Date Range")
    start_date, end_date = st.date_input(
        "Select Historical Data Range",
        value=(now - timedelta(days=2), now),
        min_value=df["timestamp"].min().date(),
        max_value=now
    )

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
df_filtered = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]

latest = df.iloc[-1]
latest_happiness = latest["happiness"]
latest_health_color = get_health_color(latest_happiness)

# --- HEADER ---
st.markdown("<h1>Plant Health Dashboard</h1>", unsafe_allow_html=True)

# --- TOP SECTION: Plant Avatar (CENTERED IMPROVEMENT) ---

# Use the middle column for centering the content
col_top = st.columns([1, 1, 1])

with col_top[1]: 
    # The 'card' div is the key container. We will use it for centering.
    st.markdown('<div class="card" style="text-align:center; padding: 2.5rem 1.5rem;">', unsafe_allow_html=True) 
    
    # 1. Title and Caption
    st.markdown("<div class='card-title'>Live Plant Avatar</div>", unsafe_allow_html=True)
    st.markdown("<div class='card-caption'>Glows based on real-time health.</div>", unsafe_allow_html=True)

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
        <div style="font-size: 38px; font-weight: 700; color: {latest_health_color}; margin-top: 15px; margin-bottom: 10px;">
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


# --- MIDDLE SECTION: 24-Hour Trends (UNCHANGED) ---
st.markdown("<h3>Sensor Trends (Current 24 Hours)</h3>", unsafe_allow_html=True)

last_24h = df[df["timestamp"] > df["timestamp"].max() - timedelta(hours=24)]
col_soil, col_light = st.columns(2)


# SOIL SENSOR
with col_soil:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Soil Moisture</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card-caption'>Current: **{latest['soil_pct']:.1f}%** (Target: {IDEAL_SOIL_MIN}% - {IDEAL_SOIL_MAX}%)</div>", unsafe_allow_html=True)
    st.markdown("<hr style='border:0;border-top:1px solid rgba(148,163,184,0.2);margin:8px 0 12px;'>", unsafe_allow_html=True)
    
    soil_fig = plot_sensor_data(last_24h, "soil_pct", "#38bdf8", IDEAL_SOIL_MIN, IDEAL_SOIL_MAX, yaxis_title="Moisture (%)")
    st.plotly_chart(soil_fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


# AMBIENT LIGHT
with col_light:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Ambient Light</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card-caption'>Current: **{latest['light_pct']:.1f}%** (LDR: {latest['light_raw']:.0f})</div>", unsafe_allow_html=True)
    st.markdown("<hr style='border:0;border-top:1px solid rgba(148,163,184,0.2);margin:8px 0 12px;'>", unsafe_allow_html=True)

    light_fig = plot_sensor_data(last_24h, "light_pct", "#facc15", yaxis_title="Light (%)")
    st.plotly_chart(light_fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


# --- BOTTOM SECTION: Correlation Analysis (UNCHANGED) ---
st.markdown("<h3>Historical Correlation Analysis</h3>", unsafe_allow_html=True)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("<div class='card-title'>Soil Moisture vs. Ambient Light</div>", unsafe_allow_html=True)
st.markdown(f"<div class='card-caption'>Overlay of key metrics over the selected range ({start_date} to {end_date}).</div>", unsafe_allow_html=True)

corr_df = df_filtered.set_index("timestamp")[["soil_pct", "light_pct"]]

corr_fig = go.Figure()
corr_fig.add_trace(go.Scatter(
    x=corr_df.index,
    y=corr_df["soil_pct"],
    mode="lines",
    name="Soil (%)",
    line=dict(width=2, color="#38bdf8")
))
corr_fig.add_trace(go.Scatter(
    x=corr_df.index,
    y=corr_df["light_pct"],
    mode="lines",
    name="Light (%)",
    line=dict(width=2, color="#facc15")
))
corr_fig.update_layout(
    height=300,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(color="#9ca3af", showgrid=False, title="Moisture/Light (%)", range=[0, 100]),
    xaxis=dict(color="#9ca3af", showgrid=False, title=""),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(corr_fig, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)