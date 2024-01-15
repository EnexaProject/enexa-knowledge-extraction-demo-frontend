import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
import time

app = dash.Dash(__name__)

app.layout = html.Div([
    html.Button('Start Process', id='btn-start-process', n_clicks=0),
    html.Label('Value: 0', id='label-value'),
    dcc.Store(id='value-store', data={'counter': 0}),
    dcc.Interval(
        id='interval-component',
        interval=1000,  # in milliseconds
        n_intervals=0
    ),
])

@app.callback(
    [Output('label-value', 'children'),
     Output('value-store', 'data')],
    [Input('btn-start-process', 'n_clicks'),
     Input('interval-component', 'n_intervals')],
    prevent_initial_call=True
)
def start_process(n_clicks, n_intervals):
    if n_clicks is None and n_intervals is None:
        raise PreventUpdate

    ctx = dash.callback_context
    stored_data = ctx.stored_data['value-store']

    if ctx.triggered_id == 'btn-start-process.n_clicks':
        # Simulating a process that takes 20 seconds
        counter_value = stored_data['counter'] + 1
        for i in range(1, 21):
            time.sleep(1)
            print(i)
            counter_value += 1

        return f'The counter is {counter_value}', {'counter': counter_value}

    raise PreventUpdate

if __name__ == '__main__':
    app.run_server(debug=True)
