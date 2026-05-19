import json

from textual import containers, events, on
from textual.app import App, ComposeResult
from textual.content import Content
from textual.reactive import reactive
from textual.widgets import Footer, Pretty, Static, TextArea


class MarkupPlayground(App):

    TITLE = "Markup Playground"
    CSS = """
    Screen {        
        layout: vertical;
        #editor {            
            width: 1fr;
            height: 1fr;
            border: tab $foreground 50%;  
            padding: 1;
            margin: 1 0 0 0;
            &:focus {
                border: tab $primary;  
            }
            
        }
        #variables {
            width: 1fr;
            height: 1fr;
            border: tab $foreground 50%;  
            padding: 1;
            margin: 1 0 0 1;
            &:focus {
                border: tab $primary;  
            }
        }
        #variables.-bad-json {
            border: tab $error;
        }
        #results-container {           
            border: tab $success;                
            &.-error {
                border: tab $error;
            }
            overflow-y: auto;
        }
        #results {                        
            padding: 1 1;            
            width: 1fr;
        }
        #spans-container {
            border: tab $success;                
            overflow-y: auto;
            margin: 0 0 0 1;
        }
        #spans {
            padding: 1 1;      
            width: 1fr;                
        }
        HorizontalGroup {
            height: 1fr;
        }
    }
    """
    AUTO_FOCUS = "#editor"

    BINDINGS = [
        ("f1", "toggle('show_variables')", "Variables"),
        ("f2", "toggle('show_spans')", "Spans"),
    ]
    variables: reactive[dict[str, object]] = reactive({})

    show_variables = reactive(True)
    show_spans = reactive(False)

    def compose(self) -> ComposeResult:
        with containers.HorizontalGroup():
            yield (editor := TextArea(id="editor", soft_wrap=False))
            yield (variables := TextArea("", id="variables", language="json"))
        editor.border_title = "Markup"
        variables.border_title = "Variables (JSON)"

        with containers.HorizontalGroup():
            with containers.VerticalScroll(id="results-container") as container:
                yield Static(id="results")
                container.border_title = "Output"
            with containers.VerticalScroll(id="spans-container") as container:
                yield Pretty([], id="spans")
                container.border_title = "Spans"

        yield Footer()







