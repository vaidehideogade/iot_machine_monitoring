import streamlit as st
import os
import pandas as pd

st.set_page_config(page_title="IoT Machine Monitoring", page_icon=":material/monitoring:", layout="wide")
title_col, bot_col = st.columns([5, 1])
with title_col:
    st.title(":material/precision_manufacturing: IoT Machine Monitoring")
    st.caption("Real-time sensor analytics from MACHINE_DATA.DATA_PIPELINE.MART")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

@st.cache_data(ttl=30)
def load_data():
    df = conn.query("SELECT * FROM MACHINE_DATA.DATA_PIPELINE.MART ORDER BY REPORT_MINUTE")
    df["REPORT_MINUTE"] = pd.to_datetime(df["REPORT_MINUTE"])
    if "TEMP_THRESHOLD_COUNT" not in df.columns:
        df["TEMP_THRESHOLD_COUNT"] = 0
    if "PRES_THRESHOLD_COUNT" not in df.columns:
        df["PRES_THRESHOLD_COUNT"] = 0
    df["TEMP_THRESHOLD_COUNT"] = df["TEMP_THRESHOLD_COUNT"].fillna(0).astype(int)
    df["PRES_THRESHOLD_COUNT"] = df["PRES_THRESHOLD_COUNT"].fillna(0).astype(int)
    return df

df = load_data()

with st.sidebar:
    st.header(":material/tune: Filters")
    temp_min, temp_max = float(df["AVG_TEMPERATURE"].min()), float(df["AVG_TEMPERATURE"].max())
    temp_range = st.slider("Temperature range (C)", min_value=temp_min, max_value=temp_max, value=(temp_min, temp_max))

    pres_min, pres_max = float(df["AVG_PRESSURE"].min()), float(df["AVG_PRESSURE"].max())
    pressure_range = st.slider("Pressure range (bar)", min_value=pres_min, max_value=pres_max, value=(pres_min, pres_max))

    st.subheader(":material/notifications_active: Thresholds")
    temp_threshold = st.number_input("Temperature alarm (C)", min_value=0.0, max_value=200.0, value=85.0, step=1.0)
    pressure_threshold = st.number_input("Pressure alarm (bar)", min_value=0.0, max_value=20.0, value=6.0, step=0.5)

    if st.button(":material/refresh: Refresh data", use_container_width=True):
        load_data.clear()
        st.rerun()

    st.caption(f"Last update: {df['REPORT_MINUTE'].max().strftime('%Y-%m-%d %H:%M')}")
    st.caption(f"Total rows: {len(df)}")

filtered = df[
    (df["AVG_TEMPERATURE"] >= temp_range[0])
    & (df["AVG_TEMPERATURE"] <= temp_range[1])
    & (df["AVG_PRESSURE"] >= pressure_range[0])
    & (df["AVG_PRESSURE"] <= pressure_range[1])
]

temp_alarm = filtered["AVG_TEMPERATURE"] > temp_threshold
pres_alarm = filtered["AVG_PRESSURE"] > pressure_threshold
alarm_count = (temp_alarm | pres_alarm).sum()

temp_sparkline = filtered.sort_values("REPORT_MINUTE")["AVG_TEMPERATURE"].tolist()[-20:]
pres_sparkline = filtered.sort_values("REPORT_MINUTE")["AVG_PRESSURE"].tolist()[-20:]

with st.container(horizontal=True):
    st.metric("Total readings", len(filtered), border=True)
    st.metric(
        "Avg temperature",
        f"{filtered['AVG_TEMPERATURE'].mean():.1f} C",
        delta=f"{filtered['AVG_TEMPERATURE'].iloc[-1] - filtered['AVG_TEMPERATURE'].mean():+.1f}",
        border=True,
        chart_data=temp_sparkline,
        chart_type="line",
    )
    st.metric(
        "Avg pressure",
        f"{filtered['AVG_PRESSURE'].mean():.2f} bar",
        delta=f"{filtered['AVG_PRESSURE'].iloc[-1] - filtered['AVG_PRESSURE'].mean():+.2f}",
        border=True,
        chart_data=pres_sparkline,
        chart_type="line",
    )
    total_alarms = int(filtered["TOTAL_ALARMS"].sum())
    total_readings = int(filtered["TOTAL_READINGS"].sum())
    alarm_rate = (total_alarms / max(total_readings, 1)) * 100
    st.metric("Alarm rate", f"{alarm_rate:.1f}%", border=True)

if alarm_count > 0:
    st.error(
        f":material/warning: **{alarm_count} records** exceed thresholds (Temp > {temp_threshold}C or Pressure > {pressure_threshold} bar)",
        icon=":material/warning:",
    )
else:
    st.success("All readings within safe limits", icon=":material/check_circle:")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader(":material/thermostat: Temperature")
        st.line_chart(filtered, x="REPORT_MINUTE", y="AVG_TEMPERATURE", color="#FF4B4B")
with col2:
    with st.container(border=True):
        st.subheader(":material/speed: Pressure")
        st.line_chart(filtered, x="REPORT_MINUTE", y="AVG_PRESSURE", color="#1f77b4")

col3, col4 = st.columns(2)
with col3:
    with st.container(border=True):
        st.subheader(":material/water_drop: Humidity")
        st.line_chart(filtered, x="REPORT_MINUTE", y="AVG_HUMIDITY", color="#2ca02c")
with col4:
    with st.container(border=True):
        st.subheader(":material/bolt: Power (kW)")
        st.line_chart(filtered, x="REPORT_MINUTE", y="AVG_POWER_KW", color="#ff7f0e")

st.subheader(":material/trending_up: Predictive alert")
last_10 = filtered.sort_values("REPORT_MINUTE").tail(10)
if len(last_10) >= 5:
    temp_trend = last_10["AVG_TEMPERATURE"].tolist()
    pres_trend = last_10["AVG_PRESSURE"].tolist()
    temp_slope = (temp_trend[-1] - temp_trend[0]) / max(len(temp_trend) - 1, 1)
    pres_slope = (pres_trend[-1] - pres_trend[0]) / max(len(pres_trend) - 1, 1)
    predicted_temp = temp_trend[-1] + (temp_slope * 5)
    predicted_pres = pres_trend[-1] + (pres_slope * 5)

    with st.container(horizontal=True):
        st.metric("Predicted temp (5 min)", f"{predicted_temp:.1f} C", delta=f"{temp_slope:+.2f} C/min", border=True)
        st.metric("Predicted pressure (5 min)", f"{predicted_pres:.2f} bar", delta=f"{pres_slope:+.3f} bar/min", border=True)

    if predicted_temp > temp_threshold or predicted_pres > pressure_threshold:
        st.error("Threshold breach predicted in next 5 minutes!", icon=":material/electric_bolt:")
    else:
        st.success("No threshold breach predicted", icon=":material/trending_flat:")
else:
    st.info("Need at least 5 readings for prediction")

st.subheader(":material/search: Anomaly detection")
if len(filtered) >= 10:
    anomaly_df = filtered.copy()
    sensors = ["AVG_TEMPERATURE", "AVG_PRESSURE", "AVG_HUMIDITY", "AVG_VIBRATION", "AVG_VOLTAGE", "AVG_CURRENT_AMP", "AVG_RPM", "AVG_POWER_KW"]
    for col_name in sensors:
        col_mean = anomaly_df[col_name].mean()
        col_std = anomaly_df[col_name].std()
        if col_std > 0:
            anomaly_df[f"{col_name}_Z"] = abs((anomaly_df[col_name] - col_mean) / col_std)
        else:
            anomaly_df[f"{col_name}_Z"] = 0.0
    z_cols = [f"{c}_Z" for c in sensors]
    anomaly_df["MAX_Z"] = anomaly_df[z_cols].max(axis=1)
    anomaly_df["ANOMALY"] = anomaly_df["MAX_Z"] > 2.0
    anomalies = anomaly_df[anomaly_df["ANOMALY"]].sort_values("MAX_Z", ascending=False)

    with st.container(horizontal=True):
        st.metric("Anomalies", len(anomalies), border=True)
        st.metric("Normal", len(anomaly_df) - len(anomalies), border=True)
        pct = (len(anomalies) / len(anomaly_df) * 100) if len(anomaly_df) > 0 else 0
        st.metric("Anomaly rate", f"{pct:.1f}%", border=True)

    if len(anomalies) > 0:
        with st.expander(f":material/table_chart: View {len(anomalies)} anomalous records"):
            st.dataframe(
                anomalies[["REPORT_MINUTE", "MACHINE_ID", "AVG_TEMPERATURE", "AVG_PRESSURE", "AVG_VIBRATION", "AVG_RPM", "MAX_Z"]].head(10),
                use_container_width=True, hide_index=True
            )
    else:
        st.success("No anomalies detected", icon=":material/check_circle:")
else:
    st.info("Need at least 10 readings for anomaly detection")

st.subheader(":material/assessment: Risk scoring")
severity_df = filtered.copy()
t_range = max(severity_df["AVG_TEMPERATURE"].max() - severity_df["AVG_TEMPERATURE"].min(), 1)
p_range = max(severity_df["AVG_PRESSURE"].max() - severity_df["AVG_PRESSURE"].min(), 1)
v_range = max(severity_df["AVG_VIBRATION"].max() - severity_df["AVG_VIBRATION"].min(), 0.001)
severity_df["RISK"] = (
    ((severity_df["AVG_TEMPERATURE"] - severity_df["AVG_TEMPERATURE"].min()) / t_range * 4) +
    ((severity_df["AVG_PRESSURE"] - severity_df["AVG_PRESSURE"].min()) / p_range * 3.5) +
    ((severity_df["AVG_VIBRATION"] - severity_df["AVG_VIBRATION"].min()) / v_range * 2.5)
).round(1)

with st.container(horizontal=True):
    st.metric("Critical (>=8)", len(severity_df[severity_df["RISK"] >= 8]), border=True)
    st.metric("High (6-8)", len(severity_df[(severity_df["RISK"] >= 6) & (severity_df["RISK"] < 8)]), border=True)
    st.metric("Medium (4-6)", len(severity_df[(severity_df["RISK"] >= 4) & (severity_df["RISK"] < 6)]), border=True)
    st.metric("Low (<4)", len(severity_df[severity_df["RISK"] < 4]), border=True)

avg_risk = severity_df["RISK"].mean()
if avg_risk >= 7:
    st.error(f"Average risk: **{avg_risk:.1f}/10** — Dangerous conditions", icon=":material/dangerous:")
elif avg_risk >= 5:
    st.warning(f"Average risk: **{avg_risk:.1f}/10** — Elevated, monitor closely", icon=":material/warning:")
else:
    st.success(f"Average risk: **{avg_risk:.1f}/10** — Acceptable levels", icon=":material/verified:")

with st.container(border=True):
    st.subheader(":material/table_chart: Raw data")
    display_df = filtered[["REPORT_MINUTE", "MACHINE_ID", "AVG_TEMPERATURE", "AVG_PRESSURE", "AVG_HUMIDITY", "AVG_VIBRATION", "AVG_VOLTAGE", "AVG_RPM", "AVG_POWER_KW", "TOTAL_ALARMS"]].copy()

    def generate_ai_message(row):
        if row["AVG_TEMPERATURE"] > temp_threshold and row["AVG_PRESSURE"] > pressure_threshold:
            return f"CRITICAL: Temp {row['AVG_TEMPERATURE']}C & Pressure {row['AVG_PRESSURE']}bar both exceed limits. Immediate action required."
        elif row["AVG_TEMPERATURE"] > temp_threshold:
            return f"WARNING: Temp {row['AVG_TEMPERATURE']}C exceeds {temp_threshold}C. Check coolant and reduce load."
        elif row["AVG_PRESSURE"] > pressure_threshold:
            return f"WARNING: Pressure {row['AVG_PRESSURE']}bar exceeds {pressure_threshold}bar. Inspect relief valve."
        return "Normal - All parameters within safe limits."

    display_df["AI_MESSAGE"] = display_df.apply(generate_ai_message, axis=1)

    def highlight_thresholds(row):
        styles = [""] * len(row)
        temp_idx = row.index.get_loc("AVG_TEMPERATURE")
        pres_idx = row.index.get_loc("AVG_PRESSURE")
        ai_idx = row.index.get_loc("AI_MESSAGE")
        if row["AVG_TEMPERATURE"] > temp_threshold:
            styles[temp_idx] = "background-color: #FF4B4B; color: white; font-weight: bold"
        if row["AVG_PRESSURE"] > pressure_threshold:
            styles[pres_idx] = "background-color: #FF4B4B; color: white; font-weight: bold"
        if row["AVG_TEMPERATURE"] > temp_threshold and row["AVG_PRESSURE"] > pressure_threshold:
            styles[ai_idx] = "background-color: #FF4B4B; color: white; font-weight: bold"
        elif row["AVG_TEMPERATURE"] > temp_threshold or row["AVG_PRESSURE"] > pressure_threshold:
            styles[ai_idx] = "background-color: #FFA500; color: white; font-weight: bold"
        return styles

    styled_df = display_df.style.apply(highlight_thresholds, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

st.subheader(":material/smart_toy: Automated insights")

tab_alert, tab_rca, tab_maint, tab_report = st.tabs([
    ":material/warning: Alerts",
    ":material/biotech: Root Cause",
    ":material/build: Maintenance",
    ":material/description: Shift Report",
])

with tab_alert:
    if alarm_count > 0:
        temp_exceeded_count = int(temp_alarm.sum())
        pres_exceeded_count = int(pres_alarm.sum())
        max_temp_val = float(filtered["AVG_TEMPERATURE"].max())
        max_pres_val = float(filtered["AVG_PRESSURE"].max())

        if temp_exceeded_count > 0 and pres_exceeded_count > 0:
            st.error(
                f"**CRITICAL:** Both thresholds breached.\n\n"
                f"- {temp_exceeded_count} temperature readings exceed {temp_threshold}C (max: {max_temp_val:.1f}C)\n"
                f"- {pres_exceeded_count} pressure readings exceed {pressure_threshold} bar (max: {max_pres_val:.2f} bar)\n\n"
                f"**Action:** Immediately reduce machine load, check cooling system and pressure relief valves.",
                icon=":material/dangerous:"
            )
        elif temp_exceeded_count > 0:
            st.warning(
                f"**WARNING:** {temp_exceeded_count} temperature readings exceed {temp_threshold}C (max: {max_temp_val:.1f}C)\n\n"
                f"**Action:** Check coolant levels, inspect heat exchangers, reduce operating speed.",
                icon=":material/warning:"
            )
        else:
            st.warning(
                f"**WARNING:** {pres_exceeded_count} pressure readings exceed {pressure_threshold} bar (max: {max_pres_val:.2f} bar)\n\n"
                f"**Action:** Inspect pressure relief valve, check for blockages, reduce feed rate.",
                icon=":material/warning:"
            )
    else:
        st.success("No alarms active — all parameters within safe operating limits.", icon=":material/check_circle:")

with tab_rca:
    if alarm_count > 0:
        alarm_rows = filtered[temp_alarm | pres_alarm].copy()
        recent_alarm = alarm_rows.sort_values("REPORT_MINUTE").tail(10)
        before_alarm = filtered[~(temp_alarm | pres_alarm)].sort_values("REPORT_MINUTE").tail(10)

        if len(before_alarm) > 0 and len(recent_alarm) > 0:
            st.markdown("**Sensor comparison: Normal vs Alarm state**")
            comparison_data = {
                "Sensor": ["Temperature (C)", "Pressure (bar)", "Vibration", "RPM", "Voltage (V)", "Power (kW)"],
                "Normal Avg": [
                    f"{before_alarm['AVG_TEMPERATURE'].mean():.1f}",
                    f"{before_alarm['AVG_PRESSURE'].mean():.2f}",
                    f"{before_alarm['AVG_VIBRATION'].mean():.4f}",
                    f"{before_alarm['AVG_RPM'].mean():.0f}",
                    f"{before_alarm['AVG_VOLTAGE'].mean():.1f}",
                    f"{before_alarm['AVG_POWER_KW'].mean():.3f}",
                ],
                "Alarm Avg": [
                    f"{recent_alarm['AVG_TEMPERATURE'].mean():.1f}",
                    f"{recent_alarm['AVG_PRESSURE'].mean():.2f}",
                    f"{recent_alarm['AVG_VIBRATION'].mean():.4f}",
                    f"{recent_alarm['AVG_RPM'].mean():.0f}",
                    f"{recent_alarm['AVG_VOLTAGE'].mean():.1f}",
                    f"{recent_alarm['AVG_POWER_KW'].mean():.3f}",
                ],
                "Delta": [
                    f"{recent_alarm['AVG_TEMPERATURE'].mean() - before_alarm['AVG_TEMPERATURE'].mean():+.1f}",
                    f"{recent_alarm['AVG_PRESSURE'].mean() - before_alarm['AVG_PRESSURE'].mean():+.2f}",
                    f"{recent_alarm['AVG_VIBRATION'].mean() - before_alarm['AVG_VIBRATION'].mean():+.4f}",
                    f"{recent_alarm['AVG_RPM'].mean() - before_alarm['AVG_RPM'].mean():+.0f}",
                    f"{recent_alarm['AVG_VOLTAGE'].mean() - before_alarm['AVG_VOLTAGE'].mean():+.1f}",
                    f"{recent_alarm['AVG_POWER_KW'].mean() - before_alarm['AVG_POWER_KW'].mean():+.3f}",
                ],
            }
            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
            deltas = {
                "Temperature": abs(recent_alarm['AVG_TEMPERATURE'].mean() - before_alarm['AVG_TEMPERATURE'].mean()),
                "Pressure": abs(recent_alarm['AVG_PRESSURE'].mean() - before_alarm['AVG_PRESSURE'].mean()) * 10,
                "Vibration": abs(recent_alarm['AVG_VIBRATION'].mean() - before_alarm['AVG_VIBRATION'].mean()) * 100,
                "RPM": abs(recent_alarm['AVG_RPM'].mean() - before_alarm['AVG_RPM'].mean()) / 50,
            }
            primary_cause = max(deltas, key=deltas.get)
            st.info(f"**Primary contributing factor:** {primary_cause} showed the largest relative change between normal and alarm states.", icon=":material/search:")
        else:
            st.info("Not enough normal readings for comparison.")
    else:
        st.success("No alarms to analyze.", icon=":material/check_circle:")

with tab_maint:
    sorted_data = filtered.sort_values("REPORT_MINUTE")
    first_half = sorted_data.head(len(sorted_data) // 2)
    second_half = sorted_data.tail(len(sorted_data) // 2)

    temp_trend_val = second_half["AVG_TEMPERATURE"].mean() - first_half["AVG_TEMPERATURE"].mean()
    pres_trend_val = second_half["AVG_PRESSURE"].mean() - first_half["AVG_PRESSURE"].mean()
    vib_trend_val = second_half["AVG_VIBRATION"].mean() - first_half["AVG_VIBRATION"].mean()
    total_alarm_count = int(filtered["TOTAL_ALARMS"].sum())

    with st.container(horizontal=True):
        st.metric("Temp trend", f"{temp_trend_val:+.1f} C", border=True)
        st.metric("Pressure trend", f"{pres_trend_val:+.2f} bar", border=True)
        st.metric("Vibration trend", f"{vib_trend_val:+.4f}", border=True)

    if temp_trend_val > 3 or pres_trend_val > 0.5 or total_alarm_count > 10:
        urgency = "Immediate" if (temp_trend_val > 5 or total_alarm_count > 20) else "Within 24 hours"
        st.error(
            f"**Urgency:** {urgency}\n\n"
            f"**Recommended tasks:**\n"
            f"- Inspect cooling system and heat exchangers\n"
            f"- Calibrate pressure relief valves\n"
            f"- Check bearings and lubrication\n"
            f"- Verify sensor accuracy\n\n"
            f"**Estimated downtime:** 2-4 hours\n\n"
            f"**Risk if delayed:** Progressive degradation leading to unplanned shutdown.",
            icon=":material/build:"
        )
    elif temp_trend_val > 1 or pres_trend_val > 0.2 or total_alarm_count > 5:
        st.warning(
            f"**Urgency:** Within 1 week\n\n"
            f"**Recommended tasks:**\n"
            f"- Routine inspection of cooling and pressure systems\n"
            f"- Lubrication check\n"
            f"- Filter replacement\n\n"
            f"**Estimated downtime:** 1-2 hours",
            icon=":material/schedule:"
        )
    else:
        st.success("**Urgency:** Routine — No significant degradation detected. Continue standard maintenance schedule.", icon=":material/verified:")

with tab_report:
    if st.button("Generate shift report"):
        total = len(filtered)
        alarm_total = int(filtered["TOTAL_ALARMS"].sum())
        temp_breaches = int((filtered["AVG_TEMPERATURE"] > temp_threshold).sum())
        pres_breaches = int((filtered["AVG_PRESSURE"] > pressure_threshold).sum())
        machine_id = filtered["MACHINE_ID"].iloc[0] if len(filtered) > 0 else "N/A"
        time_start = filtered["REPORT_MINUTE"].min().strftime("%Y-%m-%d %H:%M")
        time_end = filtered["REPORT_MINUTE"].max().strftime("%Y-%m-%d %H:%M")
        health = "Good" if alarm_total < 5 else ("Fair" if alarm_total < 15 else "Poor")

        report_text = f"""## Shift Report - {machine_id}
**Period:** {time_start} to {time_end}

### 1. Shift Overview
Machine {machine_id} operated with {total} sensor readings captured. Overall health: **{health}**.

### 2. Key Metrics
| Metric | Value |
|--------|-------|
| Total Readings | {total} |
| Avg Temperature | {filtered['AVG_TEMPERATURE'].mean():.1f} C |
| Max Temperature | {filtered['AVG_TEMPERATURE'].max():.1f} C |
| Avg Pressure | {filtered['AVG_PRESSURE'].mean():.2f} bar |
| Max Pressure | {filtered['AVG_PRESSURE'].max():.2f} bar |
| Avg Vibration | {filtered['AVG_VIBRATION'].mean():.4f} |
| Avg RPM | {filtered['AVG_RPM'].mean():.0f} |

### 3. Incidents & Alarms
- Total alarms: **{alarm_total}**
- Temperature breaches (>{temp_threshold}C): **{temp_breaches}**
- Pressure breaches (>{pressure_threshold} bar): **{pres_breaches}**

### 4. Machine Health Assessment
Status: **{health}** {'- Multiple threshold breaches detected.' if health == 'Poor' else '- Minor exceedances noted.' if health == 'Fair' else '- Operating within normal parameters.'}

### 5. Recommendations for Next Shift
{'- Immediate inspection of cooling system required' if temp_breaches > 5 else '- Continue standard monitoring'}
{'- Check pressure relief valve calibration' if pres_breaches > 3 else '- Pressure systems nominal'}
- Log any unusual sounds or vibrations
- Verify sensor readings at shift start
"""
        st.markdown(report_text)
        st.download_button(":material/download: Download report", data=report_text, file_name=f"shift_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.md", mime="text/markdown")

import math

def build_live_knowledge_base(data):
    avg_temp = float(data["AVG_TEMPERATURE"].mean())
    max_temp = float(data["AVG_TEMPERATURE"].max())
    min_temp = float(data["AVG_TEMPERATURE"].min())
    avg_pres = float(data["AVG_PRESSURE"].mean())
    max_pres = float(data["AVG_PRESSURE"].max())
    avg_hum = float(data["AVG_HUMIDITY"].mean())
    avg_vib = float(data["AVG_VIBRATION"].mean())
    max_vib = float(data["AVG_VIBRATION"].max())
    avg_volt = float(data["AVG_VOLTAGE"].mean())
    min_volt = float(data["AVG_VOLTAGE"].min())
    avg_rpm = float(data["AVG_RPM"].mean())
    avg_power = float(data["AVG_POWER_KW"].mean())
    total_alarms = int(data["TOTAL_ALARMS"].sum())
    total_readings = int(data["TOTAL_READINGS"].sum())
    alarm_rate = total_alarms / max(total_readings, 1) * 100

    sorted_data = data.sort_values("REPORT_MINUTE")
    last_10 = sorted_data.tail(10)
    last_5 = sorted_data.tail(5)
    first_half = sorted_data.head(len(sorted_data) // 2)
    second_half = sorted_data.tail(len(sorted_data) // 2)

    temp_list = last_10["AVG_TEMPERATURE"].tolist()
    pres_list = last_10["AVG_PRESSURE"].tolist()
    vib_list = last_10["AVG_VIBRATION"].tolist()
    rpm_list = last_10["AVG_RPM"].tolist()

    temp_slope = (temp_list[-1] - temp_list[0]) / max(len(temp_list) - 1, 1) if len(temp_list) >= 2 else 0
    pres_slope = (pres_list[-1] - pres_list[0]) / max(len(pres_list) - 1, 1) if len(pres_list) >= 2 else 0
    vib_slope = (vib_list[-1] - vib_list[0]) / max(len(vib_list) - 1, 1) if len(vib_list) >= 2 else 0

    latest_temp = temp_list[-1] if temp_list else avg_temp
    latest_pres = pres_list[-1] if pres_list else avg_pres
    latest_vib = vib_list[-1] if vib_list else avg_vib

    pred_temp_5 = latest_temp + temp_slope * 5
    pred_temp_10 = latest_temp + temp_slope * 10
    pred_temp_15 = latest_temp + temp_slope * 15
    pred_temp_30 = latest_temp + temp_slope * 30

    pred_pres_5 = latest_pres + pres_slope * 5
    pred_pres_10 = latest_pres + pres_slope * 10
    pred_pres_15 = latest_pres + pres_slope * 15
    pred_pres_30 = latest_pres + pres_slope * 30

    temp_trend_dir = "RISING" if temp_slope > 0.1 else "FALLING" if temp_slope < -0.1 else "STABLE"
    pres_trend_dir = "RISING" if pres_slope > 0.02 else "FALLING" if pres_slope < -0.02 else "STABLE"

    temp_breach_min = int((temp_threshold - latest_temp) / temp_slope) if temp_slope > 0 and latest_temp < temp_threshold else None
    pres_breach_min = int((pressure_threshold - latest_pres) / pres_slope) if pres_slope > 0 and latest_pres < pressure_threshold else None

    overall_temp_trend = second_half["AVG_TEMPERATURE"].mean() - first_half["AVG_TEMPERATURE"].mean()
    overall_pres_trend = second_half["AVG_PRESSURE"].mean() - first_half["AVG_PRESSURE"].mean()
    overall_vib_trend = second_half["AVG_VIBRATION"].mean() - first_half["AVG_VIBRATION"].mean()

    docs = [
        f"Machine temperature status: Current latest reading is {latest_temp:.1f}C. Average is {avg_temp:.1f}C. Maximum recorded is {max_temp:.1f}C. Minimum is {min_temp:.1f}C. Threshold is {temp_threshold}C. Status: {'EXCEEDS threshold!' if latest_temp > temp_threshold else 'Within safe range.'}",

        f"Temperature trend and prediction: Direction is {temp_trend_dir}. Rate of change is {temp_slope:+.2f}C per minute. Last 5 readings: {[round(t,1) for t in temp_list[-5:]]}. Predictions: 5min={pred_temp_5:.1f}C, 10min={pred_temp_10:.1f}C, 15min={pred_temp_15:.1f}C, 30min={pred_temp_30:.1f}C. {f'WARNING: Will breach {temp_threshold}C threshold in approximately {temp_breach_min} minutes!' if temp_breach_min and temp_breach_min < 30 else 'No breach expected in next 30 minutes.' if temp_slope <= 0 else f'At current rate, breach in ~{temp_breach_min} minutes.' if temp_breach_min else 'Already above threshold!'}",

        f"Machine pressure status: Current latest reading is {latest_pres:.2f} bar. Average is {avg_pres:.2f} bar. Maximum recorded is {max_pres:.2f} bar. Threshold is {pressure_threshold} bar. Status: {'EXCEEDS threshold!' if latest_pres > pressure_threshold else 'Within safe range.'}",

        f"Pressure trend and prediction: Direction is {pres_trend_dir}. Rate of change is {pres_slope:+.3f} bar per minute. Last 5 readings: {[round(p,2) for p in pres_list[-5:]]}. Predictions: 5min={pred_pres_5:.2f}bar, 10min={pred_pres_10:.2f}bar, 15min={pred_pres_15:.2f}bar, 30min={pred_pres_30:.2f}bar. {f'WARNING: Will breach {pressure_threshold}bar threshold in approximately {pres_breach_min} minutes!' if pres_breach_min and pres_breach_min < 30 else 'No breach expected in next 30 minutes.' if pres_slope <= 0 else f'At current rate, breach in ~{pres_breach_min} minutes.' if pres_breach_min else 'Already above threshold!'}",

        f"Machine vibration status: Current latest is {latest_vib:.4f}. Average is {avg_vib:.4f}. Maximum is {max_vib:.4f}. Normal range is 0.01-0.07. Trend: {vib_slope:+.5f} per minute. Status: {'HIGH - possible bearing wear!' if max_vib > 0.07 else 'Normal.'}",

        f"Machine power and electrical: Average voltage is {avg_volt:.1f}V, minimum {min_volt:.1f}V (normal 210-240V). Power consumption is {avg_power:.3f}kW. Average RPM is {avg_rpm:.0f} (normal 1000-1800). Last 5 RPM readings: {[round(r) for r in rpm_list[-5:]]}.",

        f"Machine humidity: Average humidity is {avg_hum:.1f}%. Optimal range is 35-65%. {'HIGH humidity risk!' if avg_hum > 65 else 'Within optimal range.' if avg_hum >= 35 else 'LOW humidity.'}",

        f"Alarm summary and history: Total alarms is {total_alarms} out of {total_readings} readings. Alarm rate is {alarm_rate:.1f}%. Recent alarm trend: first half had {int(first_half['TOTAL_ALARMS'].sum())} alarms, second half had {int(second_half['TOTAL_ALARMS'].sum())} alarms. {'Alarms INCREASING over time.' if int(second_half['TOTAL_ALARMS'].sum()) > int(first_half['TOTAL_ALARMS'].sum()) else 'Alarms decreasing or stable.'}",

        f"Overall machine health: {total_readings} readings, {total_alarms} alarms ({alarm_rate:.1f}% rate). Temperature avg {avg_temp:.1f}C (trend {overall_temp_trend:+.1f}C), Pressure avg {avg_pres:.2f}bar (trend {overall_pres_trend:+.2f}bar), Vibration avg {avg_vib:.4f} (trend {overall_vib_trend:+.4f}). Health grade: {'POOR' if alarm_rate > 30 else 'FAIR' if alarm_rate > 10 else 'GOOD'}.",

        f"Maintenance recommendation: Temperature overall trend is {overall_temp_trend:+.1f}C, Pressure trend is {overall_pres_trend:+.2f}bar, Vibration trend is {overall_vib_trend:+.4f}. {'URGENT maintenance needed - degradation detected across multiple parameters.' if (overall_temp_trend > 3 or overall_pres_trend > 0.5 or alarm_rate > 30) else 'Schedule routine maintenance within 1 week.' if (overall_temp_trend > 1 or alarm_rate > 10) else 'Machine healthy - continue standard maintenance schedule.'}",

        f"Safety status: {f'CRITICAL - temperature {max_temp:.1f}C exceeds {temp_threshold}C. ' if max_temp > temp_threshold else ''}{f'CRITICAL - pressure {max_pres:.2f}bar exceeds {pressure_threshold}bar. ' if max_pres > pressure_threshold else ''}{'All parameters within safe limits.' if max_temp <= temp_threshold and max_pres <= pressure_threshold else 'Take corrective action immediately.'}",

        f"Troubleshooting: Temperature is {'HIGH' if avg_temp > temp_threshold else 'normal'}. Pressure is {'HIGH' if avg_pres > pressure_threshold else 'normal'}. {'Both high: likely system overload - reduce load immediately.' if avg_temp > temp_threshold and avg_pres > pressure_threshold else 'Temp high only: check cooling system, coolant levels, heat exchangers.' if avg_temp > temp_threshold else 'Pressure high only: check relief valves, flow blockages, reduce feed rate.' if avg_pres > pressure_threshold else 'No issues detected - all systems normal.'}",

        f"Trend summary for all sensors: Temperature {temp_trend_dir} ({temp_slope:+.2f}C/min), Pressure {pres_trend_dir} ({pres_slope:+.3f}bar/min), Vibration trend ({vib_slope:+.5f}/min). Overall direction: {'Machine degrading - multiple parameters trending up.' if temp_slope > 0.1 and pres_slope > 0.01 else 'Machine stabilizing.' if temp_slope < 0 and pres_slope < 0 else 'Mixed trends - monitor closely.'}",
    ]
    return docs

def tokenize_text(text):
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "and", "but", "or", "not", "so", "if", "this", "that", "it", "its", "what", "how", "why", "when", "where", "which", "who", "me", "my", "your", "you", "we", "they"}
    words = text.lower().replace(".", " ").replace(",", " ").replace(":", " ").replace("-", " ").replace("(", " ").replace(")", " ").replace("/", " ").replace("?", " ").replace("!", " ").split()
    return [w for w in words if w not in stop_words and len(w) > 1]

def compute_tfidf_vectors(docs):
    doc_tokens = [tokenize_text(doc) for doc in docs]
    vocab = {}
    for tokens in doc_tokens:
        for token in tokens:
            if token not in vocab:
                vocab[token] = len(vocab)

    n_docs = len(docs)
    df_counts = {}
    for tokens in doc_tokens:
        for token in set(tokens):
            df_counts[token] = df_counts.get(token, 0) + 1

    vectors = []
    for tokens in doc_tokens:
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec = [0.0] * len(vocab)
        for token, count in tf.items():
            idx = vocab[token]
            tf_val = count / max(len(tokens), 1)
            idf_val = math.log((n_docs + 1) / (df_counts.get(token, 0) + 1)) + 1
            vec[idx] = tf_val * idf_val
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        vectors.append(vec)

    return vocab, df_counts, vectors, n_docs

def embed_query(query, vocab, df_counts, n_docs):
    tokens = tokenize_text(query)
    vec = [0.0] * len(vocab)
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    for token, count in tf.items():
        if token in vocab:
            tf_val = count / max(len(tokens), 1)
            idf_val = math.log((n_docs + 1) / (df_counts.get(token, 0) + 1)) + 1
            vec[vocab[token]] = tf_val * idf_val
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec

def cosine_sim(vec_a, vec_b):
    return sum(a * b for a, b in zip(vec_a, vec_b))

def rag_retrieve(query, docs, top_k=3):
    vocab, df_counts, doc_vectors, n_docs = compute_tfidf_vectors(docs)
    query_vector = embed_query(query, vocab, df_counts, n_docs)
    scores = [(i, cosine_sim(query_vector, dv)) for i, dv in enumerate(doc_vectors)]
    scores.sort(key=lambda x: x[1], reverse=True)
    results = []
    for idx, score in scores[:top_k]:
        if score > 0.01:
            results.append({"content": docs[idx], "score": score})
    return results

def rag_generate(query, retrieved_docs, data):
    query_lower = query.lower()
    sorted_data = data.sort_values("REPORT_MINUTE")
    last_10 = sorted_data.tail(10)

    direct_answer = ""

    import re
    time_match = re.findall(r'(\d+)\s*(?:min|minute|minutes|mins|hr|hour|hours)', query_lower)
    if not time_match:
        time_match = re.findall(r'(?:next|after|in)\s*(\d+)', query_lower)

    if time_match or any(word in query_lower for word in ["predict", "forecast", "future", "next", "will", "going", "after"]):
        minutes_ahead = [int(t) for t in time_match] if time_match else [5, 10, 15, 30]
        for i, t in enumerate(minutes_ahead):
            if "hour" in query_lower or "hr" in query_lower:
                minutes_ahead[i] = t * 60

        temp_list = last_10["AVG_TEMPERATURE"].tolist()
        pres_list = last_10["AVG_PRESSURE"].tolist()
        vib_list = last_10["AVG_VIBRATION"].tolist()

        if len(temp_list) >= 2:
            temp_slope = (temp_list[-1] - temp_list[0]) / (len(temp_list) - 1)
            pres_slope = (pres_list[-1] - pres_list[0]) / (len(pres_list) - 1)
            vib_slope = (vib_list[-1] - vib_list[0]) / (len(vib_list) - 1)

            rows = f"| Now | {temp_list[-1]:.1f}C | {pres_list[-1]:.2f} bar | {vib_list[-1]:.4f} |\n"
            for m in minutes_ahead:
                label = f"+{m} min" if m < 60 else f"+{m//60} hr"
                rows += f"| {label} | {temp_list[-1] + temp_slope*m:.1f}C | {pres_list[-1] + pres_slope*m:.2f} bar | {vib_list[-1] + vib_slope*m:.4f} |\n"

            direct_answer = f"""**Predictions based on current trend (last 10 readings):**

| Time | Temperature | Pressure | Vibration |
|------|------------|----------|-----------|
{rows}
**Rates:** Temp {temp_slope:+.2f}C/min | Pressure {pres_slope:+.3f} bar/min | Vibration {vib_slope:+.5f}/min
**Thresholds:** Temp {temp_threshold}C | Pressure {pressure_threshold} bar | Vibration 0.07"""

            for m in minutes_ahead:
                pred_t = temp_list[-1] + temp_slope * m
                pred_p = pres_list[-1] + pres_slope * m
                if pred_t > temp_threshold:
                    breach_t = int((temp_threshold - temp_list[-1]) / temp_slope) if temp_slope > 0 else 0
                    direct_answer += f"\n\n**ALERT:** Temperature will reach {pred_t:.1f}C in {m} min (breaches {temp_threshold}C in ~{breach_t} min)"
                if pred_p > pressure_threshold:
                    breach_p = int((pressure_threshold - pres_list[-1]) / pres_slope) if pres_slope > 0 else 0
                    direct_answer += f"\n\n**ALERT:** Pressure will reach {pred_p:.2f} bar in {m} min (breaches {pressure_threshold} bar in ~{breach_p} min)"

            if not any(temp_list[-1] + temp_slope*m > temp_threshold or pres_list[-1] + pres_slope*m > pressure_threshold for m in minutes_ahead):
                direct_answer += f"\n\n**All clear** — no threshold breach expected in the requested timeframe."

    elif any(word in query_lower for word in ["trend", "direction", "increasing", "decreasing", "rising", "falling", "slope"]):
        temp_list = last_10["AVG_TEMPERATURE"].tolist()
        pres_list = last_10["AVG_PRESSURE"].tolist()
        vib_list = last_10["AVG_VIBRATION"].tolist()
        rpm_list = last_10["AVG_RPM"].tolist()

        if len(temp_list) >= 2:
            temp_slope = (temp_list[-1] - temp_list[0]) / (len(temp_list) - 1)
            pres_slope = (pres_list[-1] - pres_list[0]) / (len(pres_list) - 1)
            vib_slope = (vib_list[-1] - vib_list[0]) / (len(vib_list) - 1)
            rpm_slope = (rpm_list[-1] - rpm_list[0]) / (len(rpm_list) - 1)

            def direction(slope, low=0.01):
                if slope > low:
                    return "RISING"
                elif slope < -low:
                    return "FALLING"
                return "STABLE"

            direct_answer = f"""**Current trends (based on last 10 readings):**

| Sensor | Current | Rate/min | Direction | Last 5 values |
|--------|---------|----------|-----------|---------------|
| Temperature | {temp_list[-1]:.1f}C | {temp_slope:+.2f}C | {direction(temp_slope, 0.1)} | {[round(t,1) for t in temp_list[-5:]]} |
| Pressure | {pres_list[-1]:.2f} bar | {pres_slope:+.3f} bar | {direction(pres_slope, 0.02)} | {[round(p,2) for p in pres_list[-5:]]} |
| Vibration | {vib_list[-1]:.4f} | {vib_slope:+.5f} | {direction(vib_slope, 0.001)} | {[round(v,4) for v in vib_list[-5:]]} |
| RPM | {rpm_list[-1]:.0f} | {rpm_slope:+.1f} | {direction(rpm_slope, 5)} | {[round(r) for r in rpm_list[-5:]]} |

**Overall:** {'Machine parameters trending UP - degradation possible.' if temp_slope > 0.1 and pres_slope > 0.01 else 'Machine stabilizing.' if temp_slope < 0 and pres_slope < 0 else 'Mixed trends - monitor.'}"""

    elif any(word in query_lower for word in ["status", "health", "overview", "summary", "how", "condition"]):
        total_alarms = int(data["TOTAL_ALARMS"].sum())
        total_readings = int(data["TOTAL_READINGS"].sum())
        alarm_rate = total_alarms / max(total_readings, 1) * 100
        health = "GOOD" if alarm_rate < 10 else "FAIR" if alarm_rate < 30 else "POOR"

        direct_answer = f"""**Machine Health Summary:**

| Parameter | Value | Status |
|-----------|-------|--------|
| Temperature | {data['AVG_TEMPERATURE'].mean():.1f}C (max {data['AVG_TEMPERATURE'].max():.1f}C) | {'ALERT' if data['AVG_TEMPERATURE'].max() > temp_threshold else 'OK'} |
| Pressure | {data['AVG_PRESSURE'].mean():.2f} bar (max {data['AVG_PRESSURE'].max():.2f}) | {'ALERT' if data['AVG_PRESSURE'].max() > pressure_threshold else 'OK'} |
| Vibration | {data['AVG_VIBRATION'].mean():.4f} (max {data['AVG_VIBRATION'].max():.4f}) | {'ALERT' if data['AVG_VIBRATION'].max() > 0.07 else 'OK'} |
| Voltage | {data['AVG_VOLTAGE'].mean():.1f}V (min {data['AVG_VOLTAGE'].min():.1f}V) | {'LOW' if data['AVG_VOLTAGE'].min() < 215 else 'OK'} |
| RPM | {data['AVG_RPM'].mean():.0f} | OK |
| Power | {data['AVG_POWER_KW'].mean():.3f} kW | OK |

**Alarms:** {total_alarms} / {total_readings} readings ({alarm_rate:.1f}%)
**Health Grade:** {health}"""

    if direct_answer:
        return direct_answer

    if not retrieved_docs:
        return "I couldn't find relevant information. Try asking about: **predictions, trends, machine status, temperature, pressure, vibration, alarms, maintenance, or safety.**"

    parts = []
    for doc in retrieved_docs[:2]:
        parts.append(doc["content"])
    return "\n\n".join(parts)

if "rag_history" not in st.session_state:
    st.session_state.rag_history = []

with bot_col:
    chatbot = st.popover(":material/smart_toy:", help="AI Assistant")

with chatbot:
    hdr_col, clr_col = st.columns([3, 1])
    with hdr_col:
        st.markdown("**AI Assistant (RAG)**")
    with clr_col:
        if st.button(":material/delete:", key="clear_rag", help="Clear chat"):
            st.session_state.rag_history = []
            st.rerun()

    chat_box = st.container(height=350)
    with chat_box:
        if not st.session_state.rag_history:
            st.caption("Ask about machine status, predictions, health, maintenance...")
        for msg in st.session_state.rag_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_q = st.chat_input("Type your question...", key="rag_input")
    if user_q:
        end_words = {"okay", "ok", "yes", "no", "thanks", "thank you", "bye", "done", "got it", "sure", "fine", "alright", "cool", "great", "perfect", "noted"}
        start_words = {"hi", "hello", "hey", "hii", "hiii", "start", "help", "assist"}
        if user_q.strip().lower() in end_words:
            st.session_state.rag_history.append({"role": "user", "content": user_q})
            st.session_state.rag_history.append({"role": "assistant", "content": "Got it! Let me know if you need anything else."})
            st.rerun()
        elif user_q.strip().lower() in start_words:
            st.session_state.rag_history.append({"role": "user", "content": user_q})
            st.session_state.rag_history.append({"role": "assistant", "content": "Hello! I'm your IoT Machine Assistant. Ask me about:\n- Machine temperature, pressure, vibration\n- Predictions & trends\n- Alarms & safety status\n- Maintenance recommendations\n- Machine health overview"})
            st.rerun()
        else:
            st.session_state.rag_history.append({"role": "user", "content": user_q})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(user_q)
            with st.chat_message("assistant"):
                with st.spinner("Searching..."):
                    conv_context = " ".join([m["content"] for m in st.session_state.rag_history[-4:] if m["role"] == "user"])
                    knowledge_docs = build_live_knowledge_base(filtered)
                    retrieved = rag_retrieve(conv_context, knowledge_docs)
                    answer = rag_generate(conv_context, retrieved, filtered)
                    st.markdown(answer)
                    with st.expander(":material/info: RAG details"):
                        st.caption(f"Tokens: {tokenize_text(conv_context)[:8]}")
                        st.caption(f"KB: {len(knowledge_docs)} docs | Retrieved: {len(retrieved)}")
                        for i, r in enumerate(retrieved):
                            st.caption(f"#{i+1} (sim: {r['score']:.3f})")
#Add Cortex AI Functions section
        st.session_state.rag_history.append({"role": "assistant", "content": answer})

st.subheader(":material/neurology: Snowflake AI/ML Services")

ai_tab1, ai_tab2, ai_tab3 = st.tabs([
    ":material/auto_awesome: Cortex AI Functions",
    ":material/query_stats: ML Functions",
    ":material/hub: Other Services",
])

with ai_tab1:
    st.caption("Cortex AI functions are not available on trial accounts. Upgrade to use these features.")
    st.info("AI_COMPLETE, AI_CLASSIFY, AI_FILTER, AI_AGG, AI_EMBED, AI_EXTRACT, AI_SENTIMENT, AI_SUMMARIZE_AGG, AI_SIMILARITY, AI_TRANSCRIBE, AI_PARSE_DOCUMENT, AI_REDACT, AI_TRANSLATE — all require a paid Snowflake account.", icon=":material/lock:")

with ai_tab2:
    st.caption("These ML Functions work on your trial account with live MART data.")

    ml_col1, ml_col2 = st.columns(2)
    with ml_col1:
        st.markdown("**:material/query_stats: Forecasting**")
        st.caption("Predicts future temperature values using time-series model")
        forecast_periods = st.number_input("Forecast periods (minutes ahead)", min_value=1, max_value=60, value=10)
        if st.button("Run Forecast", use_container_width=True):
            try:
                with st.spinner("Training forecast model..."):
                    session.sql("CREATE OR REPLACE VIEW MACHINE_DATA.DATA_PIPELINE.TEMP_FORECAST_VIEW AS SELECT REPORT_MINUTE AS TS, AVG_TEMPERATURE AS Y FROM MACHINE_DATA.DATA_PIPELINE.MART WHERE AVG_TEMPERATURE IS NOT NULL ORDER BY REPORT_MINUTE").collect()
                    session.sql("""
                        CREATE OR REPLACE SNOWFLAKE.ML.FORECAST MACHINE_DATA.DATA_PIPELINE.IOT_TEMP_FORECAST(
                            INPUT_DATA => SYSTEM$REFERENCE('VIEW', 'MACHINE_DATA.DATA_PIPELINE.TEMP_FORECAST_VIEW'),
                            TIMESTAMP_COLNAME => 'TS',
                            TARGET_COLNAME => 'Y'
                        )
                    """).collect()
                with st.spinner("Generating predictions..."):
                    result = session.sql(f"CALL MACHINE_DATA.DATA_PIPELINE.IOT_TEMP_FORECAST!FORECAST(FORECASTING_PERIODS => {int(forecast_periods)})").collect()
                    forecast_df = pd.DataFrame(result)
                    forecast_df = forecast_df[["TS", "FORECAST", "LOWER_BOUND", "UPPER_BOUND"]]
                    forecast_df.columns = ["Time", "Predicted Temp (C)", "Lower Bound", "Upper Bound"]
                    forecast_df["Predicted Temp (C)"] = forecast_df["Predicted Temp (C)"].round(1)
                    forecast_df["Lower Bound"] = forecast_df["Lower Bound"].round(1)
                    forecast_df["Upper Bound"] = forecast_df["Upper Bound"].round(1)
                    st.dataframe(forecast_df, use_container_width=True, hide_index=True)
                    st.line_chart(forecast_df.set_index("Time")[["Predicted Temp (C)", "Lower Bound", "Upper Bound"]])
                    st.success(f"Forecast complete! Predicted avg: {forecast_df['Predicted Temp (C)'].mean():.1f}C")
            except Exception as e:
                st.error(f"Error: {str(e)[:200]}")

    with ml_col2:
        st.markdown("**:material/search: Anomaly Detection**")
        st.caption("Detects unusual temperature readings using ML model")
        if st.button("Run Anomaly Detection", use_container_width=True):
            try:
                with st.spinner("Training anomaly model (using 80% data)..."):
                    row_count = len(filtered)
                    train_limit = int(row_count * 0.8)
                    session.sql(f"CREATE OR REPLACE VIEW MACHINE_DATA.DATA_PIPELINE.TEMP_TRAIN_VIEW AS SELECT REPORT_MINUTE AS TS, AVG_TEMPERATURE AS Y FROM MACHINE_DATA.DATA_PIPELINE.MART WHERE AVG_TEMPERATURE IS NOT NULL ORDER BY REPORT_MINUTE LIMIT {train_limit}").collect()
                    session.sql(f"CREATE OR REPLACE VIEW MACHINE_DATA.DATA_PIPELINE.TEMP_TEST_VIEW AS SELECT REPORT_MINUTE AS TS, AVG_TEMPERATURE AS Y FROM MACHINE_DATA.DATA_PIPELINE.MART WHERE AVG_TEMPERATURE IS NOT NULL ORDER BY REPORT_MINUTE DESC LIMIT {row_count - train_limit}").collect()
                    session.sql("""
                        CREATE OR REPLACE SNOWFLAKE.ML.ANOMALY_DETECTION MACHINE_DATA.DATA_PIPELINE.IOT_ANOMALY(
                            INPUT_DATA => SYSTEM$REFERENCE('VIEW', 'MACHINE_DATA.DATA_PIPELINE.TEMP_TRAIN_VIEW'),
                            TIMESTAMP_COLNAME => 'TS',
                            TARGET_COLNAME => 'Y',
                            LABEL_COLNAME => ''
                        )
                    """).collect()
                with st.spinner("Detecting anomalies in recent data..."):
                    result = session.sql("""
                        CALL MACHINE_DATA.DATA_PIPELINE.IOT_ANOMALY!DETECT_ANOMALIES(
                            INPUT_DATA => SYSTEM$REFERENCE('VIEW', 'MACHINE_DATA.DATA_PIPELINE.TEMP_TEST_VIEW'),
                            TIMESTAMP_COLNAME => 'TS',
                            TARGET_COLNAME => 'Y'
                        )
                    """).collect()
                    anomaly_df = pd.DataFrame(result)
                    anomaly_count = int(anomaly_df["IS_ANOMALY"].sum())
                    total_tested = len(anomaly_df)

                    with st.container(horizontal=True):
                        st.metric("Anomalies found", anomaly_count, border=True)
                        st.metric("Total tested", total_tested, border=True)
                        st.metric("Anomaly %", f"{anomaly_count/max(total_tested,1)*100:.0f}%", border=True)

                    display_cols = ["TS", "Y", "FORECAST", "IS_ANOMALY", "PERCENTILE"]
                    display_df = anomaly_df[display_cols].copy()
                    display_df.columns = ["Time", "Actual Temp", "Expected", "Anomaly?", "Percentile"]
                    display_df["Actual Temp"] = display_df["Actual Temp"].round(1)
                    display_df["Expected"] = display_df["Expected"].round(1)
                    st.dataframe(display_df, use_container_width=True, hide_index=True)

                    if anomaly_count > 0:
                        st.warning(f"Found {anomaly_count} anomalous readings — these deviate significantly from expected patterns.", icon=":material/warning:")
                    else:
                        st.success("No anomalies detected!", icon=":material/check_circle:")
            except Exception as e:
                st.error(f"Error: {str(e)[:200]}")

with ai_tab3:
    st.caption("These services require additional setup (accounts, compute pools, or configurations).")

    services = {
        "Cortex Agents": "Agentic AI workflows. Requires: CREATE CORTEX AGENT with tools and instructions.",
        "Cortex Analyst": "Natural language to SQL over semantic models. Requires: semantic model YAML file.",
        "Cortex Search": "Hybrid vector+keyword search for RAG. Requires: CREATE CORTEX SEARCH SERVICE on a table.",
        "Cortex Fine-tuning": "Fine-tune LLMs on your data. Requires: training data table + CORTEX.FINETUNE().",
        "Snowflake Intelligence": "High-level AI orchestration. Available in Snowsight UI.",
        "Cortex Code": "AI coding assistant. Available in Snowsight (this tool!) and CLI.",
        "Model Registry": "Register, version, and deploy custom ML models. Use snowflake.ml.registry.",
        "Feature Store": "Manage ML features with entities and feature views. Use snowflake.ml.feature_store.",
        "Cortex Guard": "Safety filtering of LLM outputs using Llama Guard. Use SNOWFLAKE.CORTEX.GUARD().",
        "REST API": "External REST endpoints for inference, embeddings, and agents. Requires API key setup.",
    }

    for name, desc in services.items():
        with st.expander(f":material/extension: {name}"):
            st.markdown(desc)
