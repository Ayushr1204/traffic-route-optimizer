import networkx as nx
import matplotlib.pyplot as plt
import heapq
import math
import numpy as np
import plotly.graph_objects as go

from neo4j import GraphDatabase
from cassandra.cluster import Cluster

# -------- DB CONNECTION --------
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "12345678"))

cluster = Cluster(['127.0.0.1'])
session = cluster.connect('traffic')


# -------- BUILD GRAPH --------
def build_graph():
    query = """
    MATCH (a:City)-[r:ROAD]->(b:City)
    RETURN a.name AS source, b.name AS target, r.road_id AS road_id
    """
    
    graph = {}

    with driver.session() as session:
        result = session.run(query)

        for record in result:
            src = record["source"]
            dst = record["target"]
            rid = record["road_id"]

            graph.setdefault(src, []).append((dst, rid))
            graph.setdefault(dst, []).append((src, rid))

    return graph

def preprocess_graph(graph, weights):
    new_graph = {}

    for city in graph:
        temp = {}

        for neighbor, road_id in graph[city]:
            if road_id not in weights:
                continue

            cost = weights[road_id]

            if neighbor not in temp or cost < temp[neighbor]:
                temp[neighbor] = cost

        new_graph[city] = [(n, c) for n, c in temp.items()]

    return new_graph


# -------- LOAD WEIGHTS --------
def load_weights(hour):
    query = """
    SELECT road_id, travel_time 
    FROM traffic_data 
    WHERE hour = %s ALLOW FILTERING
    """

    rows = session.execute(query, (hour,))

    weights = {}
    for r in rows:
        road_id, travel_time = r
        weights[road_id] = travel_time

    return weights


# -------- LOAD COORDS --------
def load_coordinates():
    query = "MATCH (c:City) RETURN c.name, c.lat, c.lon"

    coords = {}

    with driver.session() as s:
        result = s.run(query)
        for r in result:
            coords[r["c.name"]] = (r["c.lat"], r["c.lon"])

    return coords


# -------- HEURISTIC (HAVERSINE) --------
def heuristic(a, b, coords):
    if a not in coords or b not in coords:
        return 0

    lat1, lon1 = coords[a]
    lat2, lon2 = coords[b]

    R = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a_val = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))

    return R * c


# --------  --------
def dijkstra(graph, start, end):
    pq = [(0, start, [])]
    visited = set()

    while pq:
        cost, node, path = heapq.heappop(pq)

        if node in visited:
            continue

        visited.add(node)
        path = path + [node]

        if node == end:
            return cost, path

        for neighbor, weight in graph.get(node, []):
            heapq.heappush(pq, (cost + weight, neighbor, path))

    return float('inf'), []

# -------- MAIN ROUTE --------
def find_best_route_astar(source, destination, hour):
    graph = build_graph()
    weights = load_weights(hour)

    graph = preprocess_graph(graph, weights)   # ✅ CRITICAL

    coords = load_coordinates()

    cost, path = dijkstra(graph, source, destination)

    return path, cost, weights, graph, coords

# -------- ALL PATHS --------
def get_all_paths(graph, start, end, max_depth=6):
    paths = set()

    def dfs(node, path):
        if len(path) > max_depth:
            return

        if node == end:
            paths.add(tuple(path))
            return

        for neighbor, _ in graph.get(node, []):
            if neighbor not in path:
                dfs(neighbor, path + [neighbor])

    dfs(start, [start])
    return [list(p) for p in paths]


# -------- PATH COST --------
def compute_path_cost(path, graph):
    total = 0

    for i in range(len(path) - 1):
        city = path[i]
        nxt = path[i + 1]

        for neighbor, cost in graph[city]:
            if neighbor == nxt:
                total += cost
                break
        else:
            return float('inf')

    return round(total, 2)


# -------- LAYOUT --------
def get_structured_layout(G):
    import math
    pos = {}

    center = ["Nagpur", "Delhi", "Bhopal"]
    for i, n in enumerate(center):
        angle = 2 * math.pi * i / len(center)
        pos[n] = (1.5 * math.cos(angle), 1.5 * math.sin(angle))

    layer2 = ["Mumbai", "Hyderabad", "Kanpur", "Lucknow", "Indore"]
    for i, n in enumerate(layer2):
        angle = 2 * math.pi * i / len(layer2)
        pos[n] = (3 * math.cos(angle), 3 * math.sin(angle))

    layer3 = ["Bangalore", "Chennai", "Pune", "Ahmedabad", "Jaipur", "Patna", "Kolkata"]
    for i, n in enumerate(layer3):
        angle = 2 * math.pi * i / len(layer3)
        pos[n] = (5 * math.cos(angle), 5 * math.sin(angle))

    layer4 = ["Ranchi", "Bhubaneswar", "Visakhapatnam", "Coimbatore", "Kochi"]
    for i, n in enumerate(layer4):
        angle = 2 * math.pi * i / len(layer4)
        pos[n] = (7 * math.cos(angle), 7 * math.sin(angle))

    return pos


def adjust_positions(pos):
    pos = pos.copy()
    if "Ahmedabad" in pos: pos["Ahmedabad"] = (pos["Ahmedabad"][0], pos["Ahmedabad"][1] - 1)
    if "Delhi" in pos: pos["Delhi"] = (pos["Delhi"][0] - 0.3, pos["Delhi"][1] + 1.2)
    return pos


# -------- PLOTLY GRAPH --------
def plotly_graph(path, weights, graph, pos):

    def smooth(x0, y0, x1, y1, steps=10):
        return np.linspace(x0, x1, steps), np.linspace(y0, y1, steps)

    edge_x, edge_y = [], []
    seen = set()

    for city in graph:
        for neighbor, road_id in graph[city]:
            if city > neighbor:
                continue

            edge = tuple(sorted([city, neighbor]))
            if edge in seen:
                continue
            seen.add(edge)

            x0, y0 = pos[city]
            x1, y1 = pos[neighbor]

            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    edge_trace = go.Scatter(x=edge_x, y=edge_y,
                            mode='lines',
                            line=dict(width=1, color='rgba(200,200,200,0.3)'),
                            hoverinfo='none')

    # PATH
    path_x, path_y = [], []
    for i in range(len(path) - 1):
        xs, ys = smooth(*pos[path[i]], *pos[path[i+1]])
        path_x += list(xs) + [None]
        path_y += list(ys) + [None]

    path_trace = go.Scatter(x=path_x, y=path_y,
                            line=dict(width=4, color='red'),
                            mode='lines')

    # NODES
    node_x, node_y, colors = [], [], []
    for n in graph:
        x, y = pos[n]
        node_x.append(x)
        node_y.append(y)
        colors.append('orange' if n in path else '#9ecae1')

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=list(graph.keys()),
        textposition="top center",
        marker=dict(size=20, color=colors, line=dict(width=2, color='white'))
    )

    fig = go.Figure(data=[edge_trace, path_trace, node_trace])

    fig.update_layout(
        height=750,
        showlegend=False,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white")
    )

    return fig


# -------- MAP --------
def map_visualization(path, coords):
    lats, lons, valid = [], [], []

    for city in path:
        if city in coords:
            lat, lon = coords[city]
            lats.append(lat)
            lons.append(lon)
            valid.append(city)

    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lat=lats,
        lon=lons,
        mode='lines+markers',
        line=dict(width=4, color='red'),
        marker=dict(size=10),
        text=valid
    ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=sum(lats)/len(lats), lon=sum(lons)/len(lons)),
            zoom=4
        ),
        height=600,
        margin=dict(l=0, r=0, t=40, b=0)
    )

    return fig