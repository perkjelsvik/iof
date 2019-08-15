import base64
import dash_core_components as dcc
import dash_html_components as html


def app_page_layout(
    page_layout,
    app_title="Dash IoF App",
    app_name="",
    light_logo=True,
    standalone=False,
    bg_color="#506784",
    font_color="#F3F6FA",
):
    return html.Div(
        id="main_page",
        children=[
            dcc.Location(id="url", refresh=False),
            html.Div(
                id="app-page-header",
                children=[
                    html.A(
                        id="dashiof-logo",
                        children=[
                            html.Img(
                                src="data:image/png;base64,{}".format(
                                    base64.b64encode(
                                        open(
                                            "./assets/iof_icon_new_white.png", "rb"
                                        ).read()
                                    ).decode()
                                )
                            )
                        ],
                        href="/Portal" if standalone else "/dash-iof",
                    ),
                    html.H2(app_title),
                    html.A(
                        id="gh-link",
                        children=["View on GitHub"],
                        href="http://github.com/perkjelsvik/iof/",
                        style={
                            "color": "white" if light_logo else "black",
                            "border": "solid 1px white"
                            if light_logo
                            else "solid 1px black",
                        },
                    ),
                    html.Img(
                        src="data:image/png;base64,{}".format(
                            base64.b64encode(
                                open(
                                    "./assets/GitHub-Mark-{}64px.png".format(
                                        "Light-" if light_logo else ""
                                    ),
                                    "rb",
                                ).read()
                            ).decode()
                        )
                    ),
                ],
                style={"background": bg_color, "color": font_color},
            ),
            html.Div(id="app-page-content", children=page_layout),
        ],
    )


def header_colors():
    return {"bg_color": "#0F5BA7", "font_color": "white", "light_logo": True}
