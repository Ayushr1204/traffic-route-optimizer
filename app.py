import streamlit as st
import networkx as nx
import time
import numpy as np
from core import *

# ---------------- SESSION INIT ----------------
if "route_type" not in st.session_state:
    st.session_state.route_type = "best"

st.set_page_config(page_title="Traffic Optimizer", layout="wide")

# ---------------- UI FIXES ----------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 0rem;
}

h1 {
    margin-top: 0px;
    padding-top: 10px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<h1 style='text-align:center;'>🚦 Traffic Route Optimizer</h1>",
    unsafe_allow_html=True
)

# ---------------- CITY LIST ----------------
cities = [
    "Ahmedabad","Bangalore","Bhopal","Bhubaneswar","Chennai",
    "Coimbatore","Delhi","Hyderabad","Indore","Jaipur",
    "Kanpur","Kochi","Kolkata","Lucknow","Mumbai",
    "Nagpur","Patna","Pune","Ranchi","Visakhapatnam"
]

# ---------------- LAYOUT ----------------
left, right = st.columns([1.1, 2], gap="medium")

# ================= LEFT PANEL =================
with left:
    st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)

    source = st.selectbox("Source", cities)
    destination = st.selectbox("Destination", cities)

    hour = st.select_slider(
        "Hour",
        options=[0, 3, 6, 9, 12, 15, 18, 21],
        value=9
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Find Route"):
        if source == destination:
            st.warning("Source and destination cannot be the same")
            st.stop()

        path, cost, weights, graph, coords = find_best_route_astar(
            source, destination, hour
        )

        G = nx.Graph()
        for city in graph:
            for neighbor, _ in graph[city]:
                G.add_edge(city, neighbor)

        pos = adjust_positions(get_structured_layout(G))

        st.session_state.selected_path = path
        st.session_state.animation_done = False
        st.session_state.best_path = path
        st.session_state.best_cost = cost
        st.session_state.weights = weights
        st.session_state.graph = graph
        st.session_state.pos = pos
        st.session_state.cost = cost
        st.session_state.source = source
        st.session_state.destination = destination
        st.session_state.route_type = "best"

        st.rerun()

    # -------- RESULT --------
    if "selected_path" in st.session_state:

        path = st.session_state.selected_path
        cost = st.session_state.cost
        route_type = st.session_state.route_type

        if route_type == "best":
            st.success(f"Best Route:\n{' → '.join(path)}")
        else:
            st.warning(f"Alternate Route:\n{' → '.join(path)}")

        st.markdown(
            f"<div style='font-size:18px; color:#60a5fa;'>ETA: {round(cost,2)} hrs</div>",
            unsafe_allow_html=True
        )

# ================= RIGHT PANEL =================
with right:
    st.markdown("<div style='margin-top:-40px'></div>", unsafe_allow_html=True)

    if "graph" in st.session_state:
        graph = st.session_state.graph
        weights = st.session_state.weights
        pos = st.session_state.pos
    else:
        _, _, weights, graph, _ = find_best_route_astar(cities[0], cities[1], 9)
        G = nx.Graph()
        for city in graph:
            for neighbor, _ in graph[city]:
                G.add_edge(city, neighbor)
        pos = adjust_positions(get_structured_layout(G))

    placeholder = st.empty()

# -------- ANIMATION --------
def clean_layout(fig):
    fig.update_layout(
        margin=dict(l=5, r=5, t=0, b=5),
        height=500,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False)
    )
    return fig


if "selected_path" in st.session_state and not st.session_state.get("animation_done", False):

    path = st.session_state.selected_path

    # clear previous renders (important)
    placeholder.empty()

    for i in range(len(path) - 1):

        start = pos[path[i]]
        end = pos[path[i + 1]]

        # -------- LINE DRAW ANIMATION --------
        for t in np.linspace(0, 1, 25):

            # smooth easing
            t_eased = t*t if t < 0.5 else 1 - (1-t)*(1-t)

            x = start[0] + (end[0] - start[0]) * t_eased
            y = start[1] + (end[1] - start[1]) * t_eased

            fig = plotly_graph(path[:i+1], weights, graph, pos)

            fig.add_scatter(
                x=[start[0], x],
                y=[start[1], y],
                mode="lines",
                line=dict(color="#ff4d4d", width=4)
            )

            fig = clean_layout(fig)

            placeholder.plotly_chart(
                fig,
                use_container_width=True
            )

            time.sleep(0.02)

        # -------- AURA EFFECT (skip last node) --------
        if i == len(path) - 2:
            continue

        for r in range(1, 6):
            fig = plotly_graph(path[:i+2], weights, graph, pos)

            fig.add_scatter(
                x=[end[0]],
                y=[end[1]],
                mode="markers",
                marker=dict(
                    size = (20 + r*6) if i < len(path) - 2 else 20,
                    color="rgba(255,0,0,0.2)"
                )
            )

            fig = clean_layout(fig)

            placeholder.plotly_chart(
                fig,
                use_container_width=True
            )

            time.sleep(0.02)

    # prevent re-animation on rerun
    st.session_state.animation_done = True

elif "selected_path" in st.session_state:
    fig = plotly_graph(st.session_state.selected_path, weights, graph, pos)
    fig = clean_layout(fig)
    placeholder.plotly_chart(fig, use_container_width=True)

else:
    fig = plotly_graph([], weights, graph, pos)
    fig = clean_layout(fig)
    placeholder.plotly_chart(fig, use_container_width=True)

# ================= ALTERNATIVE ROUTES =================
if "selected_path" in st.session_state:

    st.subheader("🚧 Alternative Routes")

    graph = st.session_state.graph
    source = st.session_state.source
    destination = st.session_state.destination
    best_path = st.session_state.best_path
    current_cost = st.session_state.cost

    all_paths = get_all_paths(graph, source, destination)

    results = []
    for p in all_paths:
        c = compute_path_cost(p, graph)
        results.append((p, c))

    results.sort(key=lambda x: x[1])

    # ❌ remove best route completely
    filtered = []

    for p, c in results:
        if p == best_path:
            continue

        # ✅ only reasonable routes
        if c <= 1.5 * st.session_state.best_cost:
            filtered.append((p, c))

    # sort again (safety)
    filtered.sort(key=lambda x: x[1])

    # take top 5
    filtered = filtered[:5]

    for i, (p, c) in enumerate(filtered):

        col1, col2 = st.columns([8, 2])

        with col1:
            route_str = " → ".join(p)

            diff = round(c - current_cost, 2)

            if diff > 0:
                diff_text = f"(+{diff} hrs)"
            elif diff < 0:
                diff_text = f"(-{abs(diff)} hrs)"
            else:
                diff_text = "(same)"

            # ✅ SINGLE CLEAN LINE (no duplicate ETA)
            html = f"""
            <div style="display:flex; align-items:center; width:100%; padding:6px 0;">

            <div style="flex:2; text-align:left;">
            {route_str}
            </div>

            <div style="flex:1; text-align:center; color:#22c55e;">
            {round(c,2)} hrs
            </div>

            <div style="flex:1; text-align:right; color:#9ca3af;">
            {diff_text}
            </div>

            </div>
            """

            st.markdown(html, unsafe_allow_html=True)

            # ✅ highlight selected route
            if p == st.session_state.selected_path:
                st.markdown("<span style='color:#facc15;'>👉 Selected</span>", unsafe_allow_html=True)

        with col2:
            if st.button("View", key=f"alt_{i}"):
                st.session_state.selected_path = p
                st.session_state.cost = c
                st.session_state.route_type = "alternate"
                st.session_state.animation_done = False
                st.rerun()