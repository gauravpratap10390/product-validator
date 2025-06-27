from dash import html

def render_product_cards(validated_df):
    cards = []

    for i, row in enumerate(validated_df):
        card = html.Div([
            html.Div([
                html.Img(src=row.get('IMAGE_1') or '/assets/placeholder.png', style={
                    'width': '120px',
                    'height': '120px',
                    'objectFit': 'cover',
                    'border': '1px solid #ddd',
                    'borderRadius': '5px'
                })
            ], style={'flex': '0 0 130px', 'paddingRight': '15px'}),

            html.Div([
                html.H4(f"{i + 1}. {row.get('Product Name', '')}", style={'marginBottom': '10px'}),

                html.Div([
                    html.Div(f"Brand: {row.get('Brand Name', '')}", className='field-pair'),
                    html.Div(f"MRP: ₹{row.get('MRP', '')}", className='field-pair'),
                ], className='field-row'),

                html.Div([
                    html.Div(f"UOM: {row.get('uom', '')}", className='field-pair'),
                    html.Div(f"Items in Pack: {row.get('Items in Pack', '')}", className='field-pair'),
                ], className='field-row'),

                html.Div([
                    html.Div(f"Product Type: {row.get('product_type', '')}", className='field-pair'),
                    html.Div(f"Enterprise Type: {row.get('Enterprise Type', '')}", className='field-pair'),
                ], className='field-row'),

                html.P(f"Errors: {row.get('Validation Errors', '')}", style={
                    'color': 'red', 'marginBottom': '0'
                }) if row.get('Validation Errors') else None
            ], style={'flex': '1'})
        ], className='product-card')

        cards.append(card)

    return html.Div(cards)
