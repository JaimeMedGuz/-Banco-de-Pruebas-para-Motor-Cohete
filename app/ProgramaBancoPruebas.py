import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from scipy.integrate import trapezoid, cumulative_trapezoid
from PIL import Image, ImageTk
import sys, ctypes, os
import serial
import threading
import time
import serial.tools.list_ports

# ===== Configuración general =====
class Config:
    font = ('Segoe UI', 11)
    button_style = 'Custom.TButton'
    graph_size = (8, 4)
    graph_dpi = 100
    bg_color = '#f0f2f5'
    primary_color = '#007BFF'
    text_color = '#ffffff'

# ===== Colores para gráficas =====
GRAPH_COLORS = {
    'Fuerza_N': 'blue',
    'velocidad': 'green',
    'altura': 'orange',
    'impulso': 'purple'
}

# ===== Clase principal de la app =====
class BancoPruebas:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Banco de Pruebas de Motores Cohete")
        self.window.geometry("1000x800")  # Más alta la ventana
        self.window.minsize(800, 700)
        self.window.configure(bg=Config.bg_color)
        # Establece el icono de la ventana y barra de tareas (usa PNG para compatibilidad)
        try:
            icon_path_png = os.path.join(os.path.dirname(__file__), "LogoBancoPruebas.png")
            if os.path.exists(icon_path_png):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path_png), master=self.window)
                self.window.iconphoto(True, icon_img)
        except Exception as e:
            print(f"Icono no cargado: {e}")
        self.df = None
        self.archivo_cargado = None
        self.calculos = {}
        self.masa_total_inicial = 5.000
        self.masa_propelente = 0.400
        self.tiempo = None
        self.fuerza = None
        self.current_view = None
        self.graph_canvas = None
        self.serial_thread = None
        self.serial_stop_event = threading.Event()
        self.serial_port = None
        self.serial_baud = 9600
        self.serial_filename = "empuje_arduino.csv"
        self.setup_styles()
        self.create_main_menu()
        self.center_window()
        self.window.bind("<Configure>", self.on_resize)
        self.window.mainloop()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Custom.TButton', font=('Segoe UI', 10, 'bold'), padding=10,
                        background=Config.primary_color, foreground=Config.text_color,
                        borderwidth=1, focusthickness=3, focuscolor='none')
        style.map('Custom.TButton', background=[('active', '#0056b3')])

    def clear_window(self):
        for widget in self.window.winfo_children():
            widget.destroy()
        self.graph_canvas = None

    def create_main_menu(self):
        self.clear_window()
        # Frame principal con menos separación
        frame = ttk.Frame(self.window, padding="30 20 30 20")
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_view = frame

        logo = self.load_image('LogoBancoPruebas.png', (150, 150))
        if logo:
            ttk.Label(frame, image=logo).pack(pady=(0, 6))
            self.window.logo_img = logo

        ttk.Label(frame, text="Análisis de Motor Cohete", font=('Segoe UI', 16, 'bold')).pack(pady=8)

        # Formulario con menos separación
        entry_frame = ttk.Frame(frame, padding="10 5 10 5")
        entry_frame.pack(fill=tk.X, pady=8, padx=8)
        ttk.Label(entry_frame, text="Masa del cohete completo con combustible (kg):").grid(row=0, column=0, sticky="w", pady=5)
        self.masa_total_entry = ttk.Entry(entry_frame)
        self.masa_total_entry.insert(0, str(self.masa_total_inicial))
        self.masa_total_entry.grid(row=0, column=1, padx=8, sticky="ew", pady=5)
        entry_frame.columnconfigure(1, weight=1)

        ttk.Label(entry_frame, text="Masa del propelente (kg):").grid(row=1, column=0, sticky="w", pady=5)
        self.masa_prop_entry = ttk.Entry(entry_frame)
        self.masa_prop_entry.insert(0, str(self.masa_propelente))
        self.masa_prop_entry.grid(row=1, column=1, padx=8, sticky="ew", pady=5)

        archivo_txt = f"Archivo cargado: {os.path.basename(self.archivo_cargado)}" if self.archivo_cargado else "Archivo cargado: Ninguno"
        color_txt = 'green' if self.archivo_cargado else 'red'
        self.file_label = ttk.Label(frame, text=archivo_txt, font=Config.font, foreground=color_txt)
        self.file_label.pack(pady=(0, 20))  # Separación moderada debajo del label

        # Botones principales
        self.buttons = {}
        btns = [
            ("🟢 Grabar", self.mostrar_grabacion_serial),
            ("📤 Cargar CSV", self.cargar_csv),
            ("📈 Empuje", lambda: self.plot_graph('Fuerza_N', 'Empuje (N)')),
            ("🚀 Velocidad", lambda: self.plot_graph('velocidad', 'Velocidad (m/s)')),
            ("🌌 Altura", lambda: self.plot_graph('altura', 'Altura (m)')),
            ("📊 Resultados", self.mostrar_resultados),
            ("❌ Salir", self.window.destroy)
        ]
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0,0), padx=4)
        for text, cmd in btns:
            btn = ttk.Button(
                btn_frame,
                text=text,
                command=cmd,
                style=Config.button_style,
                width=14
            )
            btn.pack(fill=tk.X, pady=1, padx=1)
            self.buttons[text] = btn
            if "Cargar" not in text and "Salir" not in text and "Grabar" not in text:
                btn.config(state=tk.NORMAL if self.df is not None else tk.DISABLED)

        # Área para mostrar la grabación serial en tiempo real
        self.serial_text = tk.Text(frame, height=8, state=tk.DISABLED, font=('Consolas', 10))
        self.serial_text.pack(fill=tk.X, padx=4, pady=(8,0))

    def load_image(self, filename, size):
        try:
            path = os.path.join(os.path.dirname(__file__), filename)
            if os.path.exists(path):
                img = Image.open(path).resize(size, Image.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error cargando imagen: {e}")
        return None

    def cargar_csv(self):
        archivo = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not archivo:
            return
        try:
            df = pd.read_csv(archivo)
            df["Fuerza_N"] = df["Fuerza_kg"] * 9.81
            df["Tiempo_s"] = df["Tiempo_ms"] / 1000.0
            df = df[df["Fuerza_N"] > 0.5]
            self.tiempo = df["Tiempo_s"].values
            self.fuerza = df["Fuerza_N"].values
            self.df = df
            self.archivo_cargado = archivo
            self.file_label.config(text=f"Archivo cargado: {os.path.basename(archivo)}", foreground='green')
            self.actualizar_masas()
            self.calcular_datos()
            for text, btn in self.buttons.items():
                if "Cargar" not in text and "Salir" not in text:
                    btn.config(state=tk.NORMAL)
        except Exception as e:
            self.file_label.config(text=f"Error al cargar CSV: {e}", foreground='red')

    def actualizar_masas(self):
        try:
            self.masa_total_inicial = float(self.masa_total_entry.get())
            self.masa_propelente = float(self.masa_prop_entry.get())
        except Exception as e:
            print(f"Error actualizando masas: {e}")
 
    def calcular_datos(self):
        if self.df is None:
            return
        masa_estructura = self.masa_total_inicial - self.masa_propelente

        # --- Cálculo de masa instantánea ---
        # La masa instantánea solo disminuye durante el tiempo de quemado, luego se queda en masa_estructura.
        tiempo_quemado = self.tiempo[-1] - self.tiempo[0]
        masa_instantanea = np.array([
            self.masa_total_inicial - self.masa_propelente * ((t - self.tiempo[0]) / tiempo_quemado)
            if (t - self.tiempo[0]) <= tiempo_quemado else masa_estructura
            for t in self.tiempo
        ])


        # --- Cálculo de aceleración, velocidad y altura ---
        a = self.fuerza / masa_instantanea
        v = cumulative_trapezoid(a, self.tiempo, initial=0)
        h = cumulative_trapezoid(v, self.tiempo, initial=0)
        self.df['aceleracion'] = a
        self.df['velocidad'] = v
        self.df['altura'] = h

        # --- Altura balística después del quemado ---
        # Esto es correcto: suma la altura ganada durante el quemado y la subida balística
        v_final = v[-1]
        h_burn = h[-1]
        h_ballistic = (v_final ** 2) / (2 * 9.81)
        apogeo_total = h_burn + h_ballistic

        # --- Impulso total ---
        impulso_total = trapezoid(self.fuerza, self.tiempo)

        # --- Isp (impulso específico) ---
        # Isp = impulso_total / (masa_propelente * g)
        Isp = impulso_total / (self.masa_propelente * 9.81) if self.masa_propelente > 0 else 0

        # --- Relación empuje/peso inicial ---
        relacion_empuje_peso = self.fuerza.max() / (self.masa_total_inicial * 9.81) if self.masa_total_inicial > 0 else 0

        # --- Guardar resultados ---
        self.calculos = {
            'empuje_max': self.fuerza.max(),
            'impulso_total': impulso_total,
            'tiempo_quemado': tiempo_quemado,
            'masa_propelente': self.masa_propelente,
            'masa_estructura': masa_estructura,
            'Isp': Isp,
            'vel_final': v_final,
            'apogeo': apogeo_total,
            'tiempo_apogeo': self.tiempo[-1] + v_final / 9.81,
            'aceleracion_max': a.max(),
            'relacion_empuje_peso': relacion_empuje_peso
        }

    def mostrar_resultados(self):
        self.actualizar_masas()
        self.calcular_datos()
        self.clear_window()
        # Tarjeta visual para resultados
        card = ttk.Frame(self.window, padding=30, style="Card.TFrame")
        card.pack(fill=tk.BOTH, expand=True, padx=60, pady=40)
        style = ttk.Style()
        style.configure("Card.TFrame", background="#ffffff", relief="raised", borderwidth=2)
        style.configure("CardTitle.TLabel", font=('Segoe UI', 18, 'bold'), background="#ffffff", foreground="#007BFF")
        style.configure("CardItem.TLabel", font=('Segoe UI', 12), background="#ffffff")
        style.configure("CardValue.TLabel", font=('Segoe UI', 12, 'bold'), background="#ffffff", foreground="#007BFF")

        res = self.calculos
        # Encabezado
        ttk.Label(card, text="🚀 Resultados del Banco de Pruebas", style="CardTitle.TLabel").pack(pady=(0,15))
        # Datos principales
        items = [
            ("Empuje máximo", f"{res['empuje_max']:.2f} N"),
            ("Impulso total", f"{res['impulso_total']:.2f} N·s"),
            ("Tiempo de quemado", f"{res['tiempo_quemado']:.3f} s"),
            ("Masa de propelente", f"{res['masa_propelente']*1000:.1f} g"),
            ("Masa estructura", f"{res['masa_estructura']:.3f} kg"),
            # Elimina masa promedio
            ("Isp", f"{res['Isp']:.2f} s"),
            ("Velocidad final", f"{res['vel_final']:.2f} m/s ({res['vel_final']*3.6:.2f} km/h)"),
            ("Apogeo estimado", f"{res['apogeo']:.2f} m"),
            ("Tiempo hasta apogeo", f"{res['tiempo_apogeo']:.2f} s"),
            ("Aceleración máxima", f"{res['aceleracion_max']:.2f} m/s² ({res['aceleracion_max']/9.81:.2f} g)"),
            ("Relación empuje/peso", f"{res['relacion_empuje_peso']:.2f}")
        ]
        for label, value in items:
            row = ttk.Frame(card, style="Card.TFrame")
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=f"• {label}:", style="CardItem.TLabel", anchor="w").pack(side=tk.LEFT)
            ttk.Label(row, text=value, style="CardValue.TLabel", anchor="e").pack(side=tk.RIGHT)
        ttk.Button(card, text="⬅ Volver al menú", command=self.create_main_menu, style=Config.button_style).pack(pady=20)

    def plot_graph(self, col, ylabel):
        self.actualizar_masas()
        self.calcular_datos()
        self.clear_window()

        outer_frame = ttk.Frame(self.window)
        outer_frame.pack(fill=tk.BOTH, expand=True)

        canvas_frame = ttk.Frame(outer_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(30,10))
        canvas_frame.pack_propagate(False)

        color = GRAPH_COLORS.get(col, 'blue')
        fig, ax = plt.subplots(figsize=(6, 3), dpi=Config.graph_dpi)
        try:
            if col == 'Fuerza_N':
                ax.plot(self.tiempo, self.df[col], lw=2, color=color)
                ax.scatter(self.tiempo, self.df[col], color=color, s=10)
                max_val = self.df[col].max()
                max_time = self.tiempo[np.argmax(self.df[col])]
                unidad = "N"
            elif col == 'velocidad':
                ax.plot(self.tiempo, self.df[col], lw=2, color=color)
                max_val = self.df[col].max()
                max_time = self.tiempo[np.argmax(self.df[col])]
                unidad = "m/s"
            elif col == 'altura':
                ax.plot(self.tiempo, self.df[col], lw=2, color=color)
                max_val = self.df[col].max()
                max_time = self.tiempo[np.argmax(self.df[col])]
                unidad = "m"
            else:
                ax.plot(self.tiempo, self.df[col], lw=2, color=color)
                max_val = self.df[col].max()
                max_time = self.tiempo[np.argmax(self.df[col])]
                unidad = ""
        except KeyError:
            ttk.Label(canvas_frame, text=f"Error: columna '{col}' no encontrada. Asegúrese de cargar los datos y calcular antes.", foreground='red').pack()
            ttk.Button(canvas_frame, text="⬅ Volver al menú", command=self.create_main_menu, style=Config.button_style).pack(pady=(10,0))
            return
        fig.subplots_adjust(left=0.12, right=0.98, top=0.92, bottom=0.14)
        ax.set_title(ylabel, fontsize=11)
        ax.set_xlabel("Tiempo (s)", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.tick_params(axis='both', labelsize=9)
        ax.grid(True)
        fig.tight_layout(pad=1.0)
        self.graph_canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
        self.graph_canvas.draw()
        self.graph_canvas.get_tk_widget().pack(fill=tk.NONE, expand=False, anchor="center")

        # Label con el valor máximo alcanzado y unidad
        ttk.Label(
            canvas_frame,
            text=f"🔝 Máximo: {max_val:.2f} {unidad} en t={max_time:.2f} s",
            font=('Segoe UI', 12, 'bold'),
            foreground=color,
            background="#f8f9fa",
            padding=8
        ).pack(pady=(10,0))

        ttk.Button(canvas_frame, text="⬅ Volver al menú", command=self.create_main_menu, style=Config.button_style).pack(pady=(10,0))

    def on_resize(self, event):
        # Redibuja el gráfico si está visible y en modo gráfico
        if self.graph_canvas and self.current_view is None:
            for widget in self.window.winfo_children():
                if isinstance(widget, ttk.Frame) and widget != self.current_view:
                    widget.update_idletasks()
            # El gráfico se redibuja automáticamente con after_idle en plot_graph

    def center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def mostrar_grabacion_serial(self):
        self.clear_window()
        frame = ttk.Frame(self.window, padding="30 20 30 20")
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_view = frame

        ttk.Label(frame, text="Grabar datos Arduino", font=('Segoe UI', 16, 'bold')).pack(pady=(0,10))

        ports = [port.device for port in serial.tools.list_ports.comports()]
        port_var = tk.StringVar(value=ports[0] if ports else "")
        ttk.Label(frame, text="Puerto COM:", font=Config.font).pack(anchor="w", pady=(0,2))
        port_menu = ttk.Combobox(frame, textvariable=port_var, values=ports, state="readonly", font=Config.font)
        port_menu.pack(fill=tk.X, pady=(0,8))

        ttk.Label(frame, text="Archivo destino:", font=Config.font).pack(anchor="w", pady=(0,2))
        file_var = tk.StringVar(value=self.serial_filename)
        file_entry = ttk.Entry(frame, textvariable=file_var, font=Config.font)
        file_entry.pack(fill=tk.X, pady=(0,8))

        status_label = ttk.Label(frame, text="", foreground="blue", font=Config.font)
        status_label.pack(pady=(0,8))

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(0,8))
        btn_grabar = ttk.Button(btns, text="Iniciar grabación", style=Config.button_style)
        btn_grabar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        btn_detener = ttk.Button(btns, text="Detener grabación", style=Config.button_style, state=tk.DISABLED)
        btn_detener.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        def start_serial():
            self.serial_port = port_var.get()
            self.serial_filename = file_var.get()
            self.serial_stop_event.clear()
            self.serial_thread = threading.Thread(target=self.grabar_serial_thread, daemon=True)
            self.serial_thread.start()
            status_label.config(text=f"Grabando en {self.serial_filename} desde {self.serial_port}...")
            btn_grabar.config(state=tk.DISABLED)
            btn_detener.config(state=tk.NORMAL)

        def stop_serial():
            self.serial_stop_event.set()
            status_label.config(text="Grabación detenida.")
            btn_grabar.config(state=tk.NORMAL)
            btn_detener.config(state=tk.DISABLED)

        btn_grabar.config(command=start_serial)
        btn_detener.config(command=stop_serial)

        # Área para mostrar la grabación serial en tiempo real
        self.serial_text = tk.Text(frame, height=10, state=tk.DISABLED, font=('Consolas', 10))
        self.serial_text.pack(fill=tk.BOTH, padx=4, pady=(0,8), expand=True)

        ttk.Button(frame, text="⬅ Volver al menú", command=self.create_main_menu, style=Config.button_style).pack(pady=8)

    def grabar_serial_thread(self):
        try:
            ser = serial.Serial(self.serial_port, self.serial_baud, timeout=2)
            time.sleep(2)
            with open(self.serial_filename, "w") as f:
                while not self.serial_stop_event.is_set():
                    linea = ser.readline().decode(errors="ignore").strip()
                    if linea:
                        self.window.after(0, self.agregar_linea_serial, linea)
                        f.write(linea + "\n")
            ser.close()
        except Exception as e:
            self.window.after(0, self.agregar_linea_serial, f"Error: {e}")

    def agregar_linea_serial(self, linea):
        if hasattr(self, "serial_text"):
            self.serial_text.config(state=tk.NORMAL)
            self.serial_text.insert(tk.END, linea + "\n")
            self.serial_text.see(tk.END)
            self.serial_text.config(state=tk.DISABLED)

# ===== Ejecutar =====
if __name__ == "__main__":
    if 'win' in sys.platform:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
    try:
        BancoPruebas()
    except KeyboardInterrupt:
        print("Programa detenido por el usuario (KeyboardInterrupt).")