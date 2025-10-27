import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import httpx

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = html.Div([
    dbc.Container([
        html.H1("Nuclear Energy Forecast Platform", className="mb-4 text-center"),
        
        dbc.Row([
            dbc.Col([
                html.H3("Quick Stats"),
                html.Div(id="stats-display")
            ], width=12, className="mb-4")
        ]),
        
        dbc.Row([
            dbc.Col([
                html.H4("Nuclear Share Forecasts"),
                dcc.Graph(id="forecast-chart")
            ], width=12, className="mb-4")
        ]),
        
        dbc.Row([
            dbc.Col([
                html.H4("Market Insights"),
                html.Div(id="insights-display")
            ], width=12)
        ]),
        
        dcc.Interval(
            id='interval-component',
            interval=60000,
            n_intervals=0
        )
    ], fluid=True)
])

@app.callback(
    [Output('stats-display', 'children'),
     Output('forecast-chart', 'figure'),
     Output('insights-display', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    stats = {"Total Forecasts": "0", "Latest Data": "N/A", "Active Insights": "0"}
    
    try:
        with httpx.Client(timeout=5) as client:
            # Get status
            resp = client.get("http://localhost:8000/api/v1/admin/status")
            if resp.status_code == 200:
                data = resp.json()
                db_counts = data.get("database", {}).get("record_counts", {})
                stats["Total Forecasts"] = str(db_counts.get("nuclear_scenarios", 0))
                stats["Active Insights"] = str(db_counts.get("market_insights", 0))
                
                latest = data.get("database", {}).get("latest_summary")
                if latest:
                    stats["Latest Data"] = latest[:10]
    except Exception as e:
        print(f"Error fetching stats: {e}")
    
    # Create stats cards
    stats_cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(stats.get("Total Forecasts", "0"), className="card-title"),
                    html.P("Forecasts", className="card-text")
                ])
            ])
        ]),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(stats.get("Latest Data", "N/A"), className="card-title"),
                    html.P("Latest Data", className="card-text")
                ])
            ])
        ]),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(stats.get("Active Insights", "0"), className="card-title"),
                    html.P("Insights", className="card-text")
                ])
            ])
        ])
    ], className="g-4")
    
    # Forecast chart - get real data
    fig = go.Figure()
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get("http://localhost:8000/api/v1/forecasts/scenarios")
            if resp.status_code == 200:
                data = resp.json()
                scenarios_data = data.get("scenarios", [])
                
                # Group by scenario
                scenarios = {}
                for s in scenarios_data:
                    name = s.get("scenario_name", "unknown")
                    if name not in scenarios:
                        scenarios[name] = {"x": [], "y": []}
                    scenarios[name]["x"].append(s.get("year", 2025))
                    scenarios[name]["y"].append(s.get("nuclear_share", 0) * 100)
                
                # Add traces for each scenario
                colors = {"conservative": "red", "base": "blue", "aggressive": "green"}
                for name, data_points in scenarios.items():
                    color = colors.get(name, "gray")
                    fig.add_trace(go.Scatter(
                        x=data_points["x"],
                        y=data_points["y"],
                        name=name.title() + " Scenario",
                        line=dict(color=color, width=2)
                    ))
                
                if not scenarios:
                    # Fallback to dummy data if no scenarios
                    fig.add_trace(go.Scatter(
                        x=[2025, 2030, 2035, 2040, 2045, 2050],
                        y=[20, 25, 30, 35, 40, 45],
                        name="Base Scenario (Demo)",
                        line=dict(color='blue', width=2, dash='dash')
                    ))
    except Exception as e:
        print(f"Error fetching forecast data: {e}")
        # Fallback to dummy data
        fig.add_trace(go.Scatter(
            x=[2025, 2030, 2035, 2040, 2045, 2050],
            y=[20, 25, 30, 35, 40, 45],
            name="Base Scenario (Demo)",
            line=dict(color='blue', width=2, dash='dash')
        ))
    
    fig.update_layout(
        title="Nuclear Energy Share Projection (%)",
        xaxis_title="Year",
        yaxis_title="Nuclear Share %"
    )
    
    # Insights
    insights_html = html.P("No insights available", className="text-muted")
    
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get("http://localhost:8000/api/v1/analytics/insights?limit=5")
            if resp.status_code == 200:
                data = resp.json()
                insights_list = data.get("insights", [])
                if insights_list:
                    insights_html = html.Ul([
                        html.Li([
                            html.Strong(i["title"]),
                            ": ",
                            html.Span(i["description"][:100] + "..." if len(i["description"]) > 100 else i["description"])
                        ])
                        for i in insights_list[:5]
                    ])
    except Exception as e:
        insights_html = html.P(f"Error loading insights: {str(e)[:100]}", className="text-danger")
    
    return stats_cards, fig, insights_html

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True)
