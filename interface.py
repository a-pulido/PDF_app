import tkinter as tk
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from openai import OpenAI, RateLimitError
from pypdf import PdfReader, PdfWriter
import re, sys, os
from io import BytesIO
import threading
from dotenv import load_dotenv


class PDFAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.tasks = []
        self.n_groups = 0

        self.configure_window()
        self.configure_styles()
        self.build_ui()

    # ----------------------------------------------------
    # Window
    # ----------------------------------------------------

    def configure_window(self):
        self.root.title("PDF Analyzer")
        self.root.geometry("1000x760")
        self.root.minsize(850, 650)

        self.root.configure(bg="#F4F6F8")

    # ----------------------------------------------------
    # Styles
    # ----------------------------------------------------

    def configure_styles(self):
        style = ttk.Style()

        # "clam" allows more visual customization than
        # some platform-native ttk themes.
        style.theme_use("clam")

        style.configure(
            "App.TFrame",
            background="#F4F6F8",
        )

        style.configure(
            "Card.TFrame",
            background="white",
        )

        style.configure(
            "Title.TLabel",
            background="#F4F6F8",
            foreground="#17202A",
            font=("Segoe UI", 22, "bold"),
        )

        style.configure(
            "Subtitle.TLabel",
            background="#F4F6F8",
            foreground="#6B7280",
            font=("Segoe UI", 10),
        )

        style.configure(
            "Section.TLabel",
            background="white",
            foreground="#1F2937",
            font=("Segoe UI", 11, "bold"),
        )

        style.configure(
            "Info.TLabel",
            background="white",
            foreground="#6B7280",
            font=("Segoe UI", 9),
        )

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(18, 10),
            foreground="white",
            background="#2563EB",
            borderwidth=0,
        )

        style.map(
            "Primary.TButton",
            background=[
                ("active", "#1D4ED8"),
                ("pressed", "#1E40AF"),
            ],
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10),
            padding=(14, 8),
            foreground="#1F2937",
            background="#E5E7EB",
            borderwidth=0,
        )

        style.map(
            "Secondary.TButton",
            background=[
                ("active", "#D1D5DB"),
            ],
        )

        style.configure(
            "Modern.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground="#374151",
            font=("Segoe UI", 10),
            borderwidth=0,
            relief="flat",
        )

        style.configure(
            "Modern.Treeview.Heading",
            background="#F3F4F6",
            foreground="#374151",
            font=("Segoe UI", 10),
            padding=(0, 5),
            borderwidth=1,
            relief="flat",
        )

        style.map(
            "Modern.Treeview",
            background=[
                ("selected", "#DBEAFE"),
            ],
            foreground=[
                ("selected", "#1E3A8A"),
            ],
        )

        style.map(
            "Modern.Treeview.Heading",
            background=[
                ("active", "#E5E7EB"),
            ],
        )

        style.configure(
            "Error.TLabel",
            foreground="#B45353",
            background="white",
            font=("Segoe UI", 9)
        )

    # ----------------------------------------------------
    # UI
    # ----------------------------------------------------

    def build_ui(self):

        # ------------------------------------------------
        # Scrollable main area
        # ------------------------------------------------

        container = ttk.Frame(
            self.root,
            style="App.TFrame",
        )
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            container,
            background="#F4F6F8",
            highlightthickness=0,
        )

        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview,
        )

        canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        # This is the frame where the actual UI goes
        main = ttk.Frame(
            canvas,
            style="App.TFrame",
            padding=30,
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=main,
            anchor="nw",
        )


        # Update the canvas scrollable region whenever
        # the contents of main change size
        def update_scroll_region(event):
            canvas.configure(
                scrollregion=canvas.bbox("all")
            )


        main.bind(
            "<Configure>",
            update_scroll_region,
        )


        # Make the main frame follow the width of the canvas
        def resize_main_frame(event):
            canvas.itemconfigure(
                canvas_window,
                width=event.width,
            )


        canvas.bind(
            "<Configure>",
            resize_main_frame,
        )

        def on_mousewheel(event):
            widget = event.widget
            if isinstance(
                widget,
                (tk.Text, ttk.Treeview)
            ):
                first, last = widget.yview()

                # If the entire contents are NOT visible,
                # let this widget handle the scrolling.
                if first > 0.0 or last < 1.0:
                    return
                
            canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units"
            )


        canvas.bind_all(
            "<MouseWheel>",
            on_mousewheel,
        )

        # Header
        ttk.Label(
            main,
            text="Programa de OCR de PDFs",
            style="Title.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            main,
            text="v0.1 (Powered by ChatGPT)",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 22))

        self.task_container = ttk.Frame(
                    main,
                    style="App.TFrame",
                )
        self.task_container.pack(fill='x')

        
        self.add_task(self.task_container)

        add_task_button = ttk.Button(
                    main,
                    text="Agregar nuevo grupo de documentos",
                    command=lambda: self.add_task(self.task_container),
                    style="Secondary.TButton"
                ).pack(side="bottom")

       
    # ----------------------------------------------------
    # Actions
    # ----------------------------------------------------

    def add_task(self, task_container):
        self.n_groups += 1
        task = AnalysisTask(task_container, self.n_groups)
        self.tasks.append(task)
    

    def copy_result(self):
        result = (
            self.output_text
            .get("1.0", tk.END)
            .strip()
        )

        self.root.clipboard_clear()
        self.root.clipboard_append(result)




class AnalysisTask:
    def __init__(self, parent, i):
        self.pdf_paths = []
        self.root = parent

        self.frame = ttk.Frame(parent, style='App.TFrame')
        self.frame.pack(fill='x')

        documents_card = ttk.Frame(
            self.frame,
            style="Card.TFrame",
            padding=20,
        )
        documents_card.pack(fill="x", pady=(0, 16))

        documents_header = ttk.Frame(
            documents_card,
            style="Card.TFrame",
        )
        documents_header.pack(fill="x")

        ttk.Label(
            documents_header,
            text=f"Grupo de documentos - {i}",
            style="Section.TLabel",
        ).pack(side="left")

        self.file_count_label = ttk.Label(
            documents_header,
            text="0 PDFs seleccionados",
            style="Info.TLabel",
        )
        self.file_count_label.pack(side="right")

        tree_frame = ttk.Frame(documents_card, style="Card.TFrame")
        tree_frame.pack(fill='x')

        self.file_list = ttk.Treeview(
            tree_frame,
            columns=("file", "pages"),
            show="headings",
            style="Modern.Treeview",
            height=5
        )

        self.file_list.heading("file", text="Archivo")
        self.file_list.heading("pages", text="Páginas")

        self.file_list.column(
            "file",
            width=800,
            minwidth=300,
            stretch=True,
            anchor="w",
        )

        self.file_list.column(
            "pages",
            width=150,
            minwidth=150,
            stretch=True,
            anchor="center",
        )

        self.heading_separator = tk.Frame(
            self.file_list,
            bg="#D1D5DB",
            width=1,
        )

        def position_heading_separator(event=None):
            first_column_width = self.file_list.column(
                "file",
                "width"
            )

            self.heading_separator.place(
                x=first_column_width,
                y=0,
                width=1,
                height=34,
            )

        self.file_list.bind(
            "<Configure>",
            position_heading_separator
        )

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scrollbar.set)

        self.file_list.pack(fill='both', pady=(0,8), side='left', expand=True)
        scrollbar.pack(side='right', fill='y')
        

        buttons = ttk.Frame(
            documents_card,
            style="Card.TFrame",
        )
        buttons.pack(fill="x")

        ttk.Button(
            buttons,
            text="+ Agregar PDFs",
            style="Secondary.TButton",
            command=self.select_pdfs,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Eliminar PDF seleccionado",
            style="Secondary.TButton",
            command=self.remove_selected,
        ).pack(side="left", padx=(8, 0))

        # ------------------------------------------------
                # Prompt card
                # ------------------------------------------------
        
        prompt_card = ttk.Frame(
            self.frame,
            style="Card.TFrame",
            padding=20,
        )
        prompt_card.pack(fill="x", pady=(0, 16))

        ttk.Label(
            prompt_card,
            text="Instrucciones",
            style="Section.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            prompt_card,
            text="Formatos válidos: (1 de 10), (1 a 3 de 10)",
            style="Info.TLabel",
        ).pack(anchor="w", pady=(3, 10))

        self.input_text = ScrolledText(
            prompt_card,
            height=6,
            wrap="word",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#E5E7EB",
            highlightcolor="#2563EB",
            background="#FAFAFA",
            foreground="#111827",
            insertbackground="#111827",
            font=("Segoe UI", 10),
            padx=12,
            pady=12,
        )

        self.input_text.pack(fill="x")

        # ------------------------------------------------
        # Run area
        # ------------------------------------------------

        action_area = ttk.Frame(
            self.frame,
            style="App.TFrame",
        )                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
        action_area.pack(fill="x", pady=(0, 16))

        self.status_label = ttk.Label(
            action_area,
            text="Listo",
            style="Subtitle.TLabel",
        )
        self.status_label.pack(side="left")

        self.run_button = ttk.Button(
            action_area,
            text="Correr",
            style="Primary.TButton",
            command=self.run,
        )
        self.run_button.pack(side="right")

        # ------------------------------------------------
        # Result card
        # ------------------------------------------------

        result_card = ttk.Frame(
            self.frame,
            style="Card.TFrame",
            padding=20,
        )
        result_card.pack(
            fill="both",
            expand=True,
        )

        result_header = ttk.Frame(
            result_card,
            style="Card.TFrame",
        )
        result_header.pack(fill="x")

        ttk.Label(
            result_header,
            text="Resultado",
            style="Section.TLabel",
        ).pack(side="left")

        ttk.Button(
            result_header,
            text="Copiar",
            style="Secondary.TButton",
            command=self.copy_result,
        ).pack(side="right")

        self.error_frame = ttk.Frame(result_card, style='Card.TFrame')

        self.error_label = ttk.Label(
            self.error_frame,
            text="",
            style="Error.TLabel"
        )

        self.error_label.pack(
            anchor="w",
            pady=(0, 6)
        )

        self.output_text = ScrolledText(
            result_card,
            wrap="word",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#E5E7EB",
            background="#FAFAFA",
            foreground="#111827",
            font=("Segoe UI", 10),
            padx=12,
            pady=12,
        )

        self.output_text.pack(
            fill="both",
            expand=True,
            pady=(12, 0),
        )

        ttk.Separator(self.frame, orient='horizontal').pack(fill='x', pady=5)

    def select_pdfs(self):
        files = filedialog.askopenfilenames(
            title="Seleccionar archivos PDF",
            filetypes=[
                ("PDF files", "*.pdf")
            ],
        )

        for file in files:
            if file not in [paths['pdf_path'] for paths in self.pdf_paths]:
                filepath = Path(file)
                pdf = PdfReader(filepath)
                self.pdf_paths.append({'pdf_path':file, 'pages': len(pdf.pages)})

        self.refresh_file_list()

    def remove_selected(self):
        selected_items = self.file_list.selection()

        selected_indices = [self.file_list.index(item) for item in selected_items]

        # Remove backwards so indices don't change
        for index in sorted(selected_indices, reverse=True):
            del self.pdf_paths[index]

        self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list.delete(*self.file_list.get_children())

        for file in self.pdf_paths:
            filepath = Path(file['pdf_path'])
            filename = filepath.name
            pages = file['pages']
            self.file_list.insert(
                "",
                "end",
                values=(f"  📄  {filename}", pages)
            )
        #print(self.pdf_paths)


    def copy_result():
        pass
        
        ## TODO implement file_count_label

        # count = len(self.pdf_paths)                                                             

        # if count == 1:
        #     text = "1 PDF selected"
        # else:
        #     text = f"{count} PDFs selected"

        # self.file_count_label.config(text=text)

    def run(self):
        instructions = self.input_text.get(
            "1.0",
            tk.END
        ).strip()

        self.status_label.config(text='Procesando...')
        self.run_button.config(state='disabled')
        
        thread = threading.Thread(
            target=self.run_in_background,
            args=(instructions,),
            daemon=True
        )

        thread.start()
        

    def run_in_background(self, instructions):
        try:
            result = process_documents(
                self.pdf_paths,
                instructions
            )

            self.root.after(0, self.show_result, result)
        except OpenAILimitError as e:
            self.root.after(0, self.show_result, str(e))
            self.root.after(0, self.show_error, 'se acabaron los créditos de OpenAI')
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
        


    def show_result(self, result):

        self.output_text.delete(
            "1.0",
            tk.END
        )

        self.output_text.insert(
            tk.END,
            result
        )

        self.status_label.config(text='Completado.')
        self.run_button.config(state='normal')

    def show_error(self, error):

        self.error_label.config(
            text=f"Error: {error}"
        )

        self.error_frame.pack(fill='x', pady=(0,6), before=self.output_text)

        self.run_button.config(
            state="normal"
        )


load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

pattern = r"folio\s+(\d+)(?:\s+a\s+(\d+))?\sde\s+(\d+)"

prompt = """
    This is a scanned Spanish medical record.

    Perform OCR only.

    Extract every word exactly as it appears.

    Do not summarize.
    Do not translate.
    Do not interpret.
    Correct spelling or grammar ONLY when you are absolutely certain of what is being said.

    Attempt to read every word, even if the scan quality is poor.

    Only use [[[[ilegible]]]] when a word or phrase cannot reasonably be determined from the image. Do not use [[[[ilegible]]]] merely because the text is blurry or uncertain.

    Use the surrounding context only to distinguish visually similar characters (for example, O vs 0, l vs I, rn vs m). Do not invent words that are not supported by the image.



    Ignore headers such as clinic information. Most clinical records include a section of information at the start of each clinical record or page, this information can include but is not limited to: 

    Información del paciente. Nombre. CC. Fecha nacimiento. Edad. Sexo. Dirección. Estrato. Municipio. Teléfono(s). 
    Acompañante. Empresa. Contrato. Ocupación. Ingreso. Fecha. Hora. Fecha y hora atención. 
    Responsable. Parentesco. Dirección. Nombre de consulta. RIPS consulta. 

    The only information you should include from this section is DX principal or DX de ingreso.

    Usually medical records start with Anamnesis, Motivo de Consulta, Enfermedad actual, or Hallazgos/Interpretación if they are a medical examination such as an RMN. Use this to help you know when a medical record starts.

    Include the doctor's name in the end IN ALL CAPS.

    Ignore information that is not relevant to the current medical record.

    Fix the capitalization. Do not return full sentences in capital letters, unless they are acronyms used in medicine. 

    Add tíldes to the words that are missing them.

    Add punctuation, such as periods, commas, or colons (:) when the context calls for them, such as in line breaks of related or unrelated information.

    Return plain text only, formatted as a single paragraph."""


def process_documents(pdf_paths, instructions):
    
    ranges = []
    pdf_pages = [pdf['pages'] for pdf in pdf_paths]
    for line in instructions.splitlines():
        line = line.strip()
        if line != '':
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                #print(m.group(1), m.group(2), m.group(3))
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else start
                pages = int(m.group(3))
                if pages not in pdf_pages:
                    raise Exception('Una pagina no cuadra con las longitudes de los pdf.')
                elif end < start:
                    raise Exception(f'Por favor organice las páginas de menor a mayor: {line}')    
                ranges.append({'start':start, 'end': end, 'pages':pages, 'line':line})
            else: 
                raise Exception(f"Error en la línea: '{line}', no sigue los formatos permitidos.")

    output = ''

    for item in ranges:
        pages = item['pages']
        pdf_path_list = [pdf['pdf_path'] for pdf in pdf_paths if pdf['pages'] == pages]
        if len(pdf_path_list) != 1:
            raise Exception(f'Más de 1 PDF con {pages} páginas')
        pdf_path = pdf_path_list[0]
        start = item['start']
        end = item['end']
        line = item['line']

        pdf_bytes = extract_pdf_bytes(pdf_path, (start, end))
        try:
            processed_text = call_openai_api(pdf_bytes)
            output += line + ' ' + processed_text.output_text + '\n'
        except RateLimitError:
            print('Out of OpenAI credits')
            raise OpenAILimitError(output + line + ' ' + 'Se acabaron los creditos de OpenAI')
            #TODO test in prod
            
    return output

    



def call_openai_api(pdf_bytes):       
    uploaded = client.files.create(
        file=("record.pdf", pdf_bytes, "application/pdf"),
        purpose="user_data"
    )

    response = client.responses.create(
    model="gpt-5.5",
    input=[{
        "role":"user",
        "content":[
            {
                "type":"input_text",
                "text": prompt
            },
            {
                "type":"input_file",
                "file_id":uploaded.id
            }
            ]
        }]
    )   
    return response


def extract_pdf_bytes(pdf_path, page_range):

    reader = PdfReader(pdf_path)

    writer = PdfWriter()

    for page in range(page_range[0] - 1, page_range[1]):
        writer.add_page(reader.pages[page])

    pdf_bytes = BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes

class OpenAILimitError(Exception):
    pass


# --------------------------------------------------------
# Start application
# --------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFAnalyzerApp(root)
    root.mainloop()



