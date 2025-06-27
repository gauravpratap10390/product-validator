import dash
from dash import html, dcc, dash_table, Input, Output, State
import pandas as pd
import io
import base64
from datetime import datetime
import os
from product_cards import render_product_cards

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Product Data Validator"
server = app.server

ADDITIONAL_COLUMNS = [
    "Product Name", "Internal Part Number",
    "Brand Name", "Manufacturer Name", "MRP", "Items in Pack", "uom", "quantity uom",
    "IMAGE_1", "product_type", "Product HSN", "Enterprise Type"
]

ADMIN_USERS = ["gaurav"]
LOG_FILE_PATH = "logs/usage_log.csv"
os.makedirs("logs", exist_ok=True)

app.layout = html.Div([
    dcc.Store(id='user-role-store'),
    dcc.Store(id='reset-flag', data=False),
    dcc.Store(id='validated-data-store'),
    html.H2("🔍 Product Data Validator"),
    html.Div([
        dcc.Input(id='username-input', type='text', placeholder='Enter your username'),
        html.Button('Login', id='login-button', n_clicks=0)
    ], style={'marginBottom': '20px'}),
    html.Div(id='login-status'),
    html.Div(id='main-content')
])

master_data = pd.DataFrame()

def validate_data(product_df, master_df):
    mandatory_df = master_df[master_df['Type'].str.lower() == 'mandatory']
    mandatory_map = mandatory_df.groupby('Category Name')['Attribute Name'].apply(list).to_dict()

    value_df = master_df.dropna(subset=['Attribute Value'])
    value_map = {}
    for _, row in value_df.iterrows():
        cat = row['Category Name']
        attr = row['Attribute Name']
        values = [v.strip() for v in str(row['Attribute Value']).split(',')]
        value_map.setdefault(cat, {})[attr] = values

    def validate_row(row):
        category = row.get('Category Name Level3') or row.get('Category Name Level2')
        errors = []

        if not category:
            errors.append("Category Name Level3 and Level2 both Missing")
            return ", ".join(errors)

        required_attrs = mandatory_map.get(category, [])
        for attr in required_attrs:
            if attr not in product_df.columns:
                errors.append(f"{attr} (Missing Column)")
                continue
            value = str(row.get(attr, '')).strip()
            if value.lower() in ['', 'nan', 'none']:
                errors.append(f"{attr} Missing")

        attr_values_for_cat = value_map.get(category, {})
        for attr, valid_values in attr_values_for_cat.items():
            if attr not in product_df.columns:
                continue
            actual_value = str(row.get(attr, '')).strip()
            if actual_value.lower() in ['', 'nan', 'none']:
                continue
            if actual_value not in valid_values:
                cleaned_val = actual_value.split('.')[0] if actual_value.replace('.', '', 1).isdigit() else actual_value
                errors.append(f"{attr} >Invalid value ({cleaned_val})")

        for col in ADDITIONAL_COLUMNS:
            if col in product_df.columns:
                val = str(row.get(col, '')).strip()
                if val.lower() in ['', 'nan', 'none']:
                    errors.append(f"{col} Missing")
            else:
                errors.append(f"{col} (Missing Column)")

        try:
            mrp_value = str(row.get("MRP", "")).strip()
            if "." in mrp_value and float(mrp_value) != int(float(mrp_value)):
                errors.append("Invalid MRP: Should be integer")
        except:
            pass

        return ", ".join(errors) if errors else "No Error"

    product_df['Validation Errors'] = product_df.apply(validate_row, axis=1)
    return product_df

def log_user_activity(username, date_str, row_count):
    log_exists = os.path.exists(LOG_FILE_PATH)
    with open(LOG_FILE_PATH, 'a') as f:
        if not log_exists:
            f.write("Username,Date,Count\n")
        f.write(f"{username},{date_str},{row_count}\n")

@app.callback(
    Output('user-role-store', 'data'),
    Output('login-status', 'children'),
    Input('login-button', 'n_clicks'),
    State('username-input', 'value')
)
def login_user(n_clicks, username):
    if n_clicks and username:
        role = 'admin' if username.lower() in ADMIN_USERS else 'user'
        return role, f"✅ Logged in as {role.upper()}: {username}"
    return dash.no_update, ""

@app.callback(
    Output('main-content', 'children'),
    Input('user-role-store', 'data')
)
def render_main_content(role):
    tabs = [
        dcc.Tab(label='User (Upload Product File)', children=[
            html.Br(),
            dcc.Upload(id='upload-data', children=html.Button('📤 Upload CSV File'), multiple=False),
            html.Br(),
            html.Button("🔄 Reset", id='reset-button', n_clicks=0, style={"marginTop": "10px"}),
            html.Div(id='validation-output'),
            html.Br(),
            html.Div(id='table-preview'),
            html.A("📅 Download Validated File", id='download-link', href="", target="_blank", style={'display': 'none'})
        ]),
        dcc.Tab(label='Product Cards', children=[
            html.Div(id='product-cards-container')
        ])
    ]

    if role == 'admin':
        tabs.insert(0, dcc.Tab(label='Admin (Load Master from S3)', children=[
            html.Br(),
            dcc.Input(id='s3-url', type='text', placeholder='Paste S3 CSV URL', style={'width': '60%'}),
            html.Button("Load Master Data", id='load-button'),
            html.Div(id='load-status'),
            html.Div(id='master-preview')
        ]))
        tabs.append(dcc.Tab(label='📊 Usage Report', children=[
            html.Br(),
            html.Div(id='usage-report-table')
        ]))

    return dcc.Tabs(tabs)

@app.callback(
    Output('load-status', 'children'),
    Output('master-preview', 'children'),
    Input('load-button', 'n_clicks'),
    State('s3-url', 'value')
)
def load_master_data(n_clicks, url):
    global master_data
    if n_clicks and url:
        try:
            master_data = pd.read_csv(url)
            preview = dash_table.DataTable(
                data=master_data.head(10).to_dict('records'),
                columns=[{"name": i, "id": i} for i in master_data.columns],
                style_table={'overflowX': 'auto'}
            )
            return f"✅ Loaded {len(master_data)} rows from S3 at {datetime.now().strftime('%H:%M:%S')}", preview
        except Exception as e:
            return f"❌ Failed to load master data: {e}", None
    return "", None

@app.callback(
    Output('validation-output', 'children'),
    Output('table-preview', 'children'),
    Output('download-link', 'href'),
    Output('download-link', 'style'),
    Output('reset-flag', 'data'),
    Output('validated-data-store', 'data'),
    Input('upload-data', 'contents'),
    Input('reset-button', 'n_clicks'),
    State('upload-data', 'filename'),
    State('username-input', 'value')
)
def validate_product_data(contents, reset_clicks, filename, username):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    if triggered_id == 'reset-button':
        return "", None, "", {'display': 'none'}, True, None

    if triggered_id == 'upload-data' and contents and filename and filename.endswith('.csv'):
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        try:
            decoded_str = decoded.decode('utf-8')
        except UnicodeDecodeError:
            decoded_str = decoded.decode('latin1', errors='ignore')

        df = pd.read_csv(io.StringIO(decoded_str))

        if master_data.empty:
            return "⚠️ Please load master data first (Admin tab).", None, "", {'display': 'none'}, False, None

        validated_df = validate_data(df.copy(), master_data)

        today = datetime.now().strftime("%Y-%m-%d")
        if username:
            log_user_activity(username, today, len(validated_df))

        output = io.StringIO()
        validated_df.to_csv(output, index=False)
        download_csv = "data:text/csv;charset=utf-8," + output.getvalue()

        return f"✅ File validated successfully ({len(validated_df)} rows).", None, download_csv, {'display': 'inline-block'}, False, validated_df.to_dict('records')

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, False, dash.no_update

@app.callback(
    Output('product-cards-container', 'children'),
    Input('validated-data-store', 'data')
)
def show_product_cards(data):
    if not data:
        return html.Div("No validated data available.")
    return render_product_cards(data)

@app.callback(
    Output('usage-report-table', 'children'),
    Input('user-role-store', 'data')
)
def show_usage_report(role):
    if role != 'admin' or not os.path.exists(LOG_FILE_PATH):
        return html.Div("No usage logs available.")
    log_df = pd.read_csv(LOG_FILE_PATH)
    return dash_table.DataTable(
        data=log_df.to_dict('records'),
        columns=[{"name": i, "id": i} for i in log_df.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '5px'}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=True)
