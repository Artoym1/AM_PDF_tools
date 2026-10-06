import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from pypdf import PdfReader, PdfWriter
import io
from PIL import Image, ImageTk
from tkinterdnd2 import TkinterDnD, DND_FILES
import sys
import os
import webbrowser

# ===== Информация о программе =====
APP_NAME = "АМ PDF tools"
APP_VERSION = "1.1"
APP_AUTHOR = "Артем Моисеев, 2026 г."
APP_EMAIL = "moisar@yandex.ru"
APP_DESCRIPTION = (
    "Программа работы с PDF.\n"
    "Возможности:\n"
    "  • Объединение файлов с возможностью сортировки\n"
    "  • Разделение с возможностью сохранения в любом порядке\n"
    "  • Поворот всех или выбранных страниц внутри документа\n"
    "  • Извлечение текста (только из файлов, которые поддерживают)\n"
    "  • Удаление выбранных страниц из файла\n"
    "  • Извлечение изображений и создание PDF из картинок\n\n"
    "  • Полностью русский интерфейс\n\n"
    "Работает на Windows 7 x64 и выше."
)

# Попытка импорта PyMuPDF (только для рендеринга)
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


class PDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("850x700")
        self.root.resizable(True, True)

        self._create_menu()

        # Кеш для запоминания файлов, которые не удалось отрендерить
        self.render_fail_cache = set()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.create_merge_tab()
        self.create_split_tab()
        self.create_rotate_tab()
        self.create_text_tab()
        self.create_delete_tab()
        self.create_images_tab()

    # ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

    @staticmethod
    def parse_page_ranges(pages_str, total):
        pages = set()
        for part in pages_str.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                try:
                    a, b = part.split('-')
                    a, b = int(a), int(b)
                    if a > b:
                        a, b = b, a
                    for p in range(a, b + 1):
                        if 1 <= p <= total:
                            pages.add(p)
                except:
                    pass
            else:
                try:
                    p = int(part)
                    if 1 <= p <= total:
                        pages.add(p)
                except:
                    pass
        return sorted(pages)

    @staticmethod
    def compress_page_numbers(numbers):
        if not numbers:
            return ''
        numbers = sorted(set(numbers))
        ranges = []
        start = numbers[0]
        end = numbers[0]
        for n in numbers[1:]:
            if n == end + 1:
                end = n
            else:
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
                start = end = n
        if start == end:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{end}")
        return ','.join(ranges)

    # ================= МЕНЮ =================
    def _create_menu(self):
        """Создание строки меню."""
        menubar = tk.Menu(self.root)

        # Меню «Файл»
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Выход", command=self.root.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # Меню «Справка»
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.root.config(menu=menubar)

    def show_about(self):
        """Показ окна «О программе»."""
        about_win = tk.Toplevel(self.root)
        about_win.title("О программе")
        about_win.geometry("480x400")
        about_win.resizable(False, False)
        about_win.transient(self.root)
        about_win.grab_set()

        # Заголовок
        tk.Label(about_win, text=APP_NAME, font=("Arial", 16, "bold"), fg="#2E7D32").pack(pady=(15, 0))
        tk.Label(about_win, text=f"Версия {APP_VERSION}", font=("Arial", 10), fg="gray").pack()

        # Разделитель
        ttk.Separator(about_win, orient="horizontal").pack(fill="x", padx=20, pady=10)

        # Описание
        tk.Label(about_win, text=APP_DESCRIPTION, justify="left",
                 font=("Arial", 10), wraplength=440).pack(padx=20, anchor="w")

        # Разделитель
        ttk.Separator(about_win, orient="horizontal").pack(fill="x", padx=20, pady=10)

        # Автор
        tk.Label(about_win, text=f"Автор: {APP_AUTHOR}",
                 font=("Arial", 10, "bold")).pack(pady=(0, 2))

        # ---------- Email как кликабельная ссылка ----------
        email_label = tk.Label(
            about_win,
            text=APP_EMAIL,
            font=("Arial", 10, "underline"),
            fg="#0563C1",
            cursor="hand2"
        )
        email_label.pack(pady=(0, 5))

        # Всплывающая подсказка-статус внизу окна
        hint_label = tk.Label(about_win, text="", font=("Arial", 8), fg="gray")
        hint_label.pack(pady=(0, 2))

        def show_hint(text):
            hint_label.config(text=text)

        def clear_hint(_=None):
            hint_label.config(text="")

        email_label.bind("<Enter>", lambda e: (email_label.config(fg="#0A4B8F"),
                                                show_hint("ЛКМ — открыть почту, ПКМ — меню")), add="+")
        email_label.bind("<Leave>", lambda e: (email_label.config(fg="#0563C1"),
                                                clear_hint()), add="+")

        def open_mail_client(event=None):
            """Попытка открыть почтовый клиент + копирование в буфер."""
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(APP_EMAIL)
                self.root.update()
            except Exception:
                pass

            opened = False
            try:
                opened = webbrowser.open(f"mailto:{APP_EMAIL}")
            except Exception:
                opened = False

            if not opened:
                # Резервный способ для Windows
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(f"mailto:{APP_EMAIL}")
                        opened = True
                except Exception:
                    opened = False

            if opened:
                show_hint("Открываю почтовый клиент…")
            else:
                messagebox.showinfo(
                    "Email скопирован",
                    f"Не удалось открыть почтовый клиент (он не настроен в системе).\n\n"
                    f"Адрес скопирован в буфер обмена:\n{APP_EMAIL}"
                )

        def copy_email(event=None):
            """Копирование email в буфер обмена."""
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(APP_EMAIL)
                self.root.update()
                show_hint("Email скопирован в буфер обмена")
                about_win.after(2000, clear_hint)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось скопировать: {e}")

        # Левая кнопка мыши — открыть почтовый клиент
        email_label.bind("<Button-1>", open_mail_client)

        # Правая кнопка — контекстное меню
        email_menu = tk.Menu(about_win, tearoff=0)
        email_menu.add_command(label="Копировать email", command=copy_email)
        email_menu.add_command(label="Открыть почтовый клиент", command=open_mail_client)

        def show_email_menu(event):
            try:
                email_menu.tk_popup(event.x_root, event.y_root)
            finally:
                email_menu.grab_release()

        email_label.bind("<Button-3>", show_email_menu)
        # ---------------------------------------------------

        # Кнопка «Закрыть»
        tk.Button(about_win, text="Закрыть", width=12, command=about_win.destroy).pack(pady=15)

        # Центрирование окна относительно главного
        about_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - about_win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - about_win.winfo_height()) // 2
        about_win.geometry(f"+{x}+{y}")

    # ---------- Предпросмотр (графический или текстовый) ----------
    def show_page_preview(self, file_path, page_num, preview_label):
        """Отображает миниатюру страницы (если возможно) или текстовую информацию."""
        if not file_path or not Path(file_path).exists():
            preview_label.config(image='', text='Файл не выбран')
            return

        # Если для этого файла уже была ошибка рендеринга – сразу текст
        if file_path in self.render_fail_cache:
            self._show_text_preview(file_path, page_num, preview_label)
            return

        preview_label.config(image='', text='Загрузка...')

        # Пробуем графический рендеринг
        if HAS_FITZ:
            try:
                doc = fitz.open(file_path)
                if 1 <= page_num <= len(doc):
                    page = doc[page_num - 1]
                    # Целевой размер миниатюры (пропорции А4)
                    target_width = 250
                    target_height = 350
                    scale_x = target_width / page.rect.width
                    scale_y = target_height / page.rect.height
                    scale = min(scale_x, scale_y)
                    if scale > 1:
                        scale = 1.0  # не увеличиваем
                    mat = fitz.Matrix(scale, scale)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    photo = ImageTk.PhotoImage(img)
                    preview_label.config(image=photo, text='')
                    preview_label.image = photo
                else:
                    preview_label.config(text='Страница вне диапазона', image='')
                doc.close()
                return  # успех
            except Exception:
                # Ошибка рендеринга – запоминаем файл и переходим к тексту
                self.render_fail_cache.add(file_path)
                self._show_text_preview(file_path, page_num, preview_label)
        else:
            # Библиотека не установлена
            preview_label.config(text='(установите PyMuPDF\nдля визуального предпросмотра)', image='')

    def _show_text_preview(self, file_path, page_num, preview_label):
        """Показывает текстовую информацию о странице."""
        try:
            reader = PdfReader(file_path)
            total = len(reader.pages)
            if 1 <= page_num <= total:
                page = reader.pages[page_num - 1]
                width = page.mediabox.width
                height = page.mediabox.height
                preview_label.config(
                    image='',
                    text=f"Страница {page_num} из {total}\n"
                         f"Размер: {width:.0f} x {height:.0f} pt"
                )
            else:
                preview_label.config(text='Страница вне диапазона', image='')
        except Exception as e:
            preview_label.config(text=f'Ошибка: {str(e)[:50]}', image='')

    def populate_page_list(self, file_path, listbox, preview_label):
        listbox.delete(0, tk.END)
        if not file_path or not Path(file_path).exists():
            return
        try:
            reader = PdfReader(file_path)
            total = len(reader.pages)
            for i in range(1, total + 1):
                listbox.insert(tk.END, f"Стр. {i}")
            if total > 0:
                self.show_page_preview(file_path, 1, preview_label)
                listbox.selection_set(0)
        except Exception:
            pass

    def update_range_from_selection(self, listbox, entry_var):
        selected = listbox.curselection()
        if not selected:
            entry_var.set('')
            return
        numbers = []
        for idx in selected:
            text = listbox.get(idx)
            try:
                num = int(text.split()[1])
                numbers.append(num)
            except:
                pass
        if numbers:
            entry_var.set(self.compress_page_numbers(numbers))
        else:
            entry_var.set('')

    # ---------- Обработчики дропа ----------
    def on_drop_files_list(self, event, listbox, preview_label=None):
        files = self.root.tk.splitlist(event.data)
        if files:
            for f in files:
                listbox.insert(tk.END, f)
            if preview_label and listbox.size() > 0:
                first_file = listbox.get(0)
                if Path(first_file).exists():
                    self.show_page_preview(first_file, 1, preview_label)

    # ---------------------- Объединение ----------------------
    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if files:
            for f in files:
                self.merge_file_list.insert(tk.END, f)

    def move_up(self):
        selected = self.merge_file_list.curselection()
        if not selected:
            return
        index = selected[0]
        if index == 0:
            return
        text = self.merge_file_list.get(index)
        prev_text = self.merge_file_list.get(index - 1)
        self.merge_file_list.delete(index - 1, index)
        self.merge_file_list.insert(index - 1, text, prev_text)
        self.merge_file_list.selection_set(index - 1)

    def move_down(self):
        selected = self.merge_file_list.curselection()
        if not selected:
            return
        index = selected[0]
        if index == self.merge_file_list.size() - 1:
            return
        text = self.merge_file_list.get(index)
        next_text = self.merge_file_list.get(index + 1)
        self.merge_file_list.delete(index, index + 1)
        self.merge_file_list.insert(index, next_text, text)
        self.merge_file_list.selection_set(index + 1)

    def remove_selected(self):
        selected = self.merge_file_list.curselection()
        if selected:
            for i in reversed(selected):
                self.merge_file_list.delete(i)

    def merge_action(self):
        files = list(self.merge_file_list.get(0, tk.END))
        if not files:
            messagebox.showwarning("Внимание", "Выберите файлы для объединения")
            return
        out_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out_path:
            return
        try:
            writer = PdfWriter()
            for f in files:
                reader = PdfReader(f)
                for page in reader.pages:
                    writer.add_page(page)
            with open(out_path, "wb") as f_out:
                writer.write(f_out)
            messagebox.showinfo("Готово", f"Файл сохранён:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def on_merge_select(self, event):
        selected = self.merge_file_list.curselection()
        if not selected:
            return
        index = selected[0]
        file_path = self.merge_file_list.get(index)
        if file_path and Path(file_path).exists():
            self.show_page_preview(file_path, 1, self.merge_preview_label)

    # ---------------------- Разделение ----------------------
    def split_action(self):
        in_file = self.split_in_file.get()
        if not in_file:
            messagebox.showwarning("Внимание", "Выберите исходный PDF")
            return
        if self.split_mode_var.get() == "all":
            out_dir = filedialog.askdirectory()
            if not out_dir:
                return
            try:
                reader = PdfReader(in_file)
                out_dir = Path(out_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                for i, page in enumerate(reader.pages, start=1):
                    writer = PdfWriter()
                    writer.add_page(page)
                    with open(out_dir / f"page_{i:03d}.pdf", "wb") as f:
                        writer.write(f)
                messagebox.showinfo("Готово", f"Страницы сохранены в папке:\n{out_dir}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
        else:
            pages_str = self.page_range_var.get()
            out_file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
            if not out_file:
                return
            try:
                reader = PdfReader(in_file)
                total = len(reader.pages)
                selected = self.parse_page_ranges(pages_str, total)
                if not selected:
                    messagebox.showwarning("Внимание", "Не выбрано ни одной корректной страницы")
                    return
                writer = PdfWriter()
                for p in selected:
                    writer.add_page(reader.pages[p - 1])
                with open(out_file, "wb") as f:
                    writer.write(f)
                messagebox.showinfo("Готово", f"Извлечено страниц: {len(selected)}\nФайл: {out_file}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    # ---------------------- Поворот ----------------------
    def rotate_action(self):
        in_file = self.rotate_in_file.get()
        if not in_file:
            messagebox.showwarning("Внимание", "Выберите PDF")
            return
        angle = self.rotate_angle_var.get()
        pages_str = self.rotate_pages_var.get() if self.rotate_scope_var.get() == "range" else ""
        out_file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out_file:
            return
        try:
            reader = PdfReader(in_file)
            total = len(reader.pages)
            writer = PdfWriter()
            if pages_str.strip():
                selected = self.parse_page_ranges(pages_str, total)
                if not selected:
                    messagebox.showwarning("Внимание", "Нет корректных страниц")
                    return
            else:
                selected = list(range(1, total + 1))
            for i, page in enumerate(reader.pages, start=1):
                if i in selected:
                    page.rotate(angle)
                writer.add_page(page)
            with open(out_file, "wb") as f:
                writer.write(f)
            messagebox.showinfo("Готово", f"Файл сохранён:\n{out_file}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------------------- Извлечение текста ----------------------
    def extract_text_action(self):
        in_file = self.text_in_file.get()
        if not in_file:
            messagebox.showwarning("Внимание", "Выберите PDF")
            return
        pages_str = self.text_pages_var.get() if self.text_scope_var.get() == "range" else ""
        try:
            reader = PdfReader(in_file)
            total = len(reader.pages)
            if pages_str.strip():
                selected = self.parse_page_ranges(pages_str, total)
                if not selected:
                    messagebox.showwarning("Внимание", "Нет корректных страниц")
                    return
            else:
                selected = list(range(1, total + 1))
            full_text = []
            for p in selected:
                text = reader.pages[p - 1].extract_text()
                if text:
                    full_text.append(f"=== Страница {p} ===\n{text}")
                else:
                    full_text.append(f"=== Страница {p} ===\n[Текст отсутствует]")
            result = "\n\n".join(full_text)
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert("1.0", result)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def save_text(self):
        text = self.text_output.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Внимание", "Нет текста для сохранения")
            return
        out_file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if out_file:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Готово", f"Текст сохранён:\n{out_file}")

    # ---------------------- Удаление страниц ----------------------
    def delete_pages_action(self):
        in_file = self.delete_in_file.get()
        if not in_file:
            messagebox.showwarning("Внимание", "Выберите исходный PDF")
            return
        pages_str = self.delete_pages_var.get().strip()
        if not pages_str:
            messagebox.showwarning("Внимание", "Укажите диапазоны страниц для удаления")
            return
        out_file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out_file:
            return
        try:
            reader = PdfReader(in_file)
            total = len(reader.pages)
            to_delete = self.parse_page_ranges(pages_str, total)
            if not to_delete:
                messagebox.showwarning("Внимание", "Нет корректных страниц для удаления")
                return
            writer = PdfWriter()
            for i, page in enumerate(reader.pages, start=1):
                if i not in to_delete:
                    writer.add_page(page)
            if len(writer.pages) == 0:
                messagebox.showwarning("Внимание", "После удаления не осталось страниц")
                return
            with open(out_file, "wb") as f:
                writer.write(f)
            messagebox.showinfo("Готово", f"Удалено страниц: {len(to_delete)}\nОсталось: {len(writer.pages)}\nФайл: {out_file}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------------------- Работа с изображениями ----------------------
    def extract_images_action(self):
        in_file = self.img_extract_in_file.get()
        if not in_file:
            messagebox.showwarning("Внимание", "Выберите исходный PDF")
            return
        out_dir = filedialog.askdirectory(title="Выберите папку для сохранения изображений")
        if not out_dir:
            return
        pages_str = self.img_extract_pages_var.get().strip() if self.img_extract_scope_var.get() == "range" else ""
        try:
            reader = PdfReader(in_file)
            total = len(reader.pages)
            if pages_str:
                selected = self.parse_page_ranges(pages_str, total)
                if not selected:
                    messagebox.showwarning("Внимание", "Нет корректных страниц")
                    return
            else:
                selected = list(range(1, total + 1))

            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            count = 0
            for p in selected:
                page = reader.pages[p - 1]
                try:
                    for img_name, img_obj in page.images.items():
                        data = img_obj.data
                        ext = Path(img_name).suffix.lower()
                        if ext not in ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'):
                            ext = '.png'
                        out_path = out_dir / f"page_{p:03d}_{Path(img_name).stem}{ext}"
                        try:
                            img = Image.open(io.BytesIO(data))
                            img.save(out_path)
                            count += 1
                        except:
                            pass
                except:
                    continue
            if count == 0:
                messagebox.showinfo("Результат", "Не найдено изображений на указанных страницах")
            else:
                messagebox.showinfo("Готово", f"Извлечено изображений: {count}\nПапка: {out_dir}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def select_images_files(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
        )
        if files:
            for f in files:
                self.img_create_list.insert(tk.END, f)

    def img_move_up(self):
        selected = self.img_create_list.curselection()
        if not selected:
            return
        index = selected[0]
        if index == 0:
            return
        text = self.img_create_list.get(index)
        prev_text = self.img_create_list.get(index - 1)
        self.img_create_list.delete(index - 1, index)
        self.img_create_list.insert(index - 1, text, prev_text)
        self.img_create_list.selection_set(index - 1)

    def img_move_down(self):
        selected = self.img_create_list.curselection()
        if not selected:
            return
        index = selected[0]
        if index == self.img_create_list.size() - 1:
            return
        text = self.img_create_list.get(index)
        next_text = self.img_create_list.get(index + 1)
        self.img_create_list.delete(index, index + 1)
        self.img_create_list.insert(index, next_text, text)
        self.img_create_list.selection_set(index + 1)

    def img_remove_selected(self):
        selected = self.img_create_list.curselection()
        if selected:
            for i in reversed(selected):
                self.img_create_list.delete(i)

    def create_pdf_from_images_action(self):
        files = list(self.img_create_list.get(0, tk.END))
        if not files:
            messagebox.showwarning("Внимание", "Выберите изображения для создания PDF")
            return
        out_file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out_file:
            return
        try:
            images = []
            for f in files:
                try:
                    img = Image.open(f)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    images.append(img)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось открыть {f}:\n{e}")
                    return
            if images:
                images[0].save(out_file, save_all=True, append_images=images[1:])
                messagebox.showinfo("Готово", f"PDF создан из {len(images)} изображений:\n{out_file}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ===================== ПОСТРОЕНИЕ ИНТЕРФЕЙСА =====================

    # ----- Объединить -----
    def create_merge_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Объединить")
        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill='both', expand=True)

        main_frame = ttk.Frame(frm)
        main_frame.pack(fill='both', expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        ttk.Label(left_frame, text="Список PDF для объединения:").pack(anchor='w')
        top_btn_frame = ttk.Frame(left_frame)
        top_btn_frame.pack(fill='x', pady=2)
        ttk.Button(top_btn_frame, text="Добавить файлы", command=self.select_files).pack(side='left', padx=5)
        ttk.Button(top_btn_frame, text="Очистить список", command=lambda: self.merge_file_list.delete(0, tk.END)).pack(side='left')
        ttk.Button(top_btn_frame, text="Удалить выбранное", command=self.remove_selected).pack(side='left', padx=5)

        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill='both', expand=True, pady=5)
        self.merge_file_list = tk.Listbox(list_frame, height=12, selectmode=tk.EXTENDED)
        self.merge_file_list.pack(side='left', fill='both', expand=True)
        # Дроп для списка с обновлением предпросмотра
        self.merge_file_list.drop_target_register(DND_FILES)
        self.merge_file_list.dnd_bind('<<Drop>>', lambda e: self.on_drop_files_list(e, self.merge_file_list, self.merge_preview_label))
        self.merge_file_list.bind('<<ListboxSelect>>', self.on_merge_select)

        order_btn_frame = ttk.Frame(list_frame)
        order_btn_frame.pack(side='right', fill='y', padx=5)
        ttk.Button(order_btn_frame, text="▲ Вверх", command=self.move_up).pack(pady=2)
        ttk.Button(order_btn_frame, text="▼ Вниз", command=self.move_down).pack(pady=2)

        right_frame = ttk.Frame(main_frame, padding=(10, 0, 0, 0))
        right_frame.pack(side='right', fill='both', expand=False)
        ttk.Label(right_frame, text="Предпросмотр", font=('', 10, 'bold')).pack(anchor='w')
        self.merge_preview_label = ttk.Label(right_frame, text="Выберите файл", anchor='center', justify='center')
        self.merge_preview_label.pack(pady=5, fill='both', expand=True)

        ttk.Button(frm, text="Объединить в...", command=self.merge_action).pack(pady=10)

    # ----- Разделить -----
    def create_split_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Разделить")
        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill='both', expand=True)

        main_frame = ttk.Frame(frm)
        main_frame.pack(fill='both', expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        ttk.Label(left_frame, text="Исходный PDF:").pack(anchor='w')
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(fill='x', pady=2)
        self.split_in_file = tk.StringVar()
        entry = ttk.Entry(file_frame, textvariable=self.split_in_file, width=40)
        entry.pack(side='left', expand=True, fill='x')
        # Дроп с вызовом split_load_pdf
        entry.drop_target_register(DND_FILES)
        entry.dnd_bind('<<Drop>>', self.split_drop_handler)
        ttk.Button(file_frame, text="Обзор", command=self.split_load_pdf).pack(side='left', padx=5)

        self.split_mode_var = tk.StringVar(value="all")
        self.split_mode_var.trace_add('write', self.split_mode_changed)
        ttk.Radiobutton(left_frame, text="Все страницы в отдельные файлы", variable=self.split_mode_var, value="all").pack(anchor='w')
        ttk.Radiobutton(left_frame, text="Выбранный диапазон в один файл", variable=self.split_mode_var, value="range").pack(anchor='w')

        range_frame = ttk.Frame(left_frame)
        range_frame.pack(fill='x', pady=2)
        ttk.Label(range_frame, text="Диапазоны (напр. 1-3,5,7-9):").pack(side='left')
        self.page_range_var = tk.StringVar()
        ttk.Entry(range_frame, textvariable=self.page_range_var, width=20).pack(side='left', padx=5)

        ttk.Button(left_frame, text="Разделить...", command=self.split_action).pack(pady=10)

        right_frame = ttk.Frame(main_frame, padding=(10, 0, 0, 0))
        right_frame.pack(side='right', fill='both', expand=False)

        ttk.Label(right_frame, text="Страницы", font=('', 10, 'bold')).pack(anchor='w')
        self.split_page_listbox = tk.Listbox(right_frame, height=12, width=10, selectmode=tk.EXTENDED)
        self.split_page_listbox.pack(fill='both', expand=True, pady=2)
        self.split_page_listbox.bind('<<ListboxSelect>>', self.split_on_page_select)

        ttk.Label(right_frame, text="Предпросмотр", font=('', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        self.split_preview_label = ttk.Label(right_frame, text="Выберите файл", anchor='center', justify='center')
        self.split_preview_label.pack(pady=5, fill='both', expand=True)

    def split_drop_handler(self, event):
        # Получаем путь из дропа и вызываем загрузку
        files = self.root.tk.splitlist(event.data)
        if files:
            self.split_in_file.set(files[0])
            self.split_load_pdf()  # обновляем список страниц и предпросмотр

    def split_load_pdf(self):
        file_path = self.split_in_file.get()
        if file_path:
            self.populate_page_list(file_path, self.split_page_listbox, self.split_preview_label)
            if self.split_mode_var.get() == "range":
                self.update_range_from_selection(self.split_page_listbox, self.page_range_var)

    def split_mode_changed(self, *args):
        if self.split_mode_var.get() == "range":
            self.update_range_from_selection(self.split_page_listbox, self.page_range_var)

    def split_on_page_select(self, event):
        if self.split_mode_var.get() == "range":
            self.update_range_from_selection(self.split_page_listbox, self.page_range_var)
        selected = self.split_page_listbox.curselection()
        if selected:
            idx = selected[0]
            file_path = self.split_in_file.get()
            if file_path and Path(file_path).exists():
                self.show_page_preview(file_path, idx + 1, self.split_preview_label)

    # ----- Поворот -----
    def create_rotate_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Поворот")
        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill='both', expand=True)

        main_frame = ttk.Frame(frm)
        main_frame.pack(fill='both', expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        ttk.Label(left_frame, text="Исходный PDF:").pack(anchor='w')
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(fill='x', pady=2)
        self.rotate_in_file = tk.StringVar()
        entry = ttk.Entry(file_frame, textvariable=self.rotate_in_file, width=40)
        entry.pack(side='left', expand=True, fill='x')
        entry.drop_target_register(DND_FILES)
        entry.dnd_bind('<<Drop>>', self.rotate_drop_handler)
        ttk.Button(file_frame, text="Обзор", command=self.rotate_load_pdf).pack(side='left', padx=5)

        ttk.Label(left_frame, text="Угол поворота:").pack(anchor='w')
        self.rotate_angle_var = tk.IntVar(value=90)
        angles = ttk.Frame(left_frame)
        angles.pack(anchor='w')
        for a in (90, 180, 270):
            ttk.Radiobutton(angles, text=f"{a}°", variable=self.rotate_angle_var, value=a).pack(side='left', padx=10)

        self.rotate_scope_var = tk.StringVar(value="all")
        self.rotate_scope_var.trace_add('write', self.rotate_scope_changed)
        ttk.Radiobutton(left_frame, text="Все страницы", variable=self.rotate_scope_var, value="all").pack(anchor='w')
        ttk.Radiobutton(left_frame, text="Только указанные", variable=self.rotate_scope_var, value="range").pack(anchor='w')
        range_frame = ttk.Frame(left_frame)
        range_frame.pack(fill='x', pady=2)
        ttk.Label(range_frame, text="Диапазоны:").pack(side='left')
        self.rotate_pages_var = tk.StringVar()
        ttk.Entry(range_frame, textvariable=self.rotate_pages_var, width=20).pack(side='left', padx=5)

        ttk.Button(left_frame, text="Повернуть и сохранить...", command=self.rotate_action).pack(pady=10)

        right_frame = ttk.Frame(main_frame, padding=(10, 0, 0, 0))
        right_frame.pack(side='right', fill='both', expand=False)

        ttk.Label(right_frame, text="Страницы", font=('', 10, 'bold')).pack(anchor='w')
        self.rotate_page_listbox = tk.Listbox(right_frame, height=12, width=10, selectmode=tk.EXTENDED)
        self.rotate_page_listbox.pack(fill='both', expand=True, pady=2)
        self.rotate_page_listbox.bind('<<ListboxSelect>>', self.rotate_on_page_select)

        ttk.Label(right_frame, text="Предпросмотр", font=('', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        self.rotate_preview_label = ttk.Label(right_frame, text="Выберите файл", anchor='center', justify='center')
        self.rotate_preview_label.pack(pady=5, fill='both', expand=True)

    def rotate_drop_handler(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.rotate_in_file.set(files[0])
            self.rotate_load_pdf()

    def rotate_load_pdf(self):
        file_path = self.rotate_in_file.get()
        if file_path:
            self.populate_page_list(file_path, self.rotate_page_listbox, self.rotate_preview_label)
            if self.rotate_scope_var.get() == "range":
                self.update_range_from_selection(self.rotate_page_listbox, self.rotate_pages_var)

    def rotate_scope_changed(self, *args):
        if self.rotate_scope_var.get() == "range":
            self.update_range_from_selection(self.rotate_page_listbox, self.rotate_pages_var)

    def rotate_on_page_select(self, event):
        if self.rotate_scope_var.get() == "range":
            self.update_range_from_selection(self.rotate_page_listbox, self.rotate_pages_var)
        selected = self.rotate_page_listbox.curselection()
        if selected:
            idx = selected[0]
            file_path = self.rotate_in_file.get()
            if file_path and Path(file_path).exists():
                self.show_page_preview(file_path, idx + 1, self.rotate_preview_label)

    # ----- Извлечение текста -----
    def create_text_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Извлечь текст")
        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill='both', expand=True)

        main_frame = ttk.Frame(frm)
        main_frame.pack(fill='both', expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        ttk.Label(left_frame, text="Исходный PDF:").pack(anchor='w')
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(fill='x', pady=2)
        self.text_in_file = tk.StringVar()
        entry = ttk.Entry(file_frame, textvariable=self.text_in_file, width=40)
        entry.pack(side='left', expand=True, fill='x')
        entry.drop_target_register(DND_FILES)
        entry.dnd_bind('<<Drop>>', self.text_drop_handler)
        ttk.Button(file_frame, text="Обзор", command=self.text_load_pdf).pack(side='left', padx=5)

        self.text_scope_var = tk.StringVar(value="all")
        self.text_scope_var.trace_add('write', self.text_scope_changed)
        ttk.Radiobutton(left_frame, text="Все страницы", variable=self.text_scope_var, value="all").pack(anchor='w')
        ttk.Radiobutton(left_frame, text="Определённые страницы", variable=self.text_scope_var, value="range").pack(anchor='w')
        range_frame = ttk.Frame(left_frame)
        range_frame.pack(fill='x', pady=2)
        ttk.Label(range_frame, text="Диапазоны:").pack(side='left')
        self.text_pages_var = tk.StringVar()
        ttk.Entry(range_frame, textvariable=self.text_pages_var, width=20).pack(side='left', padx=5)

        ttk.Button(left_frame, text="Извлечь", command=self.extract_text_action).pack(pady=5)
        text_frame = ttk.Frame(left_frame)
        text_frame.pack(fill='both', expand=True)
        self.text_output = tk.Text(text_frame, wrap='word', height=10)
        scroll = ttk.Scrollbar(text_frame, command=self.text_output.yview)
        self.text_output.configure(yscrollcommand=scroll.set)
        self.text_output.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        ttk.Button(left_frame, text="Сохранить текст в файл...", command=self.save_text).pack(pady=10)

        right_frame = ttk.Frame(main_frame, padding=(10, 0, 0, 0))
        right_frame.pack(side='right', fill='both', expand=False)

        ttk.Label(right_frame, text="Страницы", font=('', 10, 'bold')).pack(anchor='w')
        self.text_page_listbox = tk.Listbox(right_frame, height=12, width=10, selectmode=tk.EXTENDED)
        self.text_page_listbox.pack(fill='both', expand=True, pady=2)
        self.text_page_listbox.bind('<<ListboxSelect>>', self.text_on_page_select)

        ttk.Label(right_frame, text="Предпросмотр", font=('', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        self.text_preview_label = ttk.Label(right_frame, text="Выберите файл", anchor='center', justify='center')
        self.text_preview_label.pack(pady=5, fill='both', expand=True)

    def text_drop_handler(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.text_in_file.set(files[0])
            self.text_load_pdf()

    def text_load_pdf(self):
        file_path = self.text_in_file.get()
        if file_path:
            self.populate_page_list(file_path, self.text_page_listbox, self.text_preview_label)
            if self.text_scope_var.get() == "range":
                self.update_range_from_selection(self.text_page_listbox, self.text_pages_var)

    def text_scope_changed(self, *args):
        if self.text_scope_var.get() == "range":
            self.update_range_from_selection(self.text_page_listbox, self.text_pages_var)

    def text_on_page_select(self, event):
        if self.text_scope_var.get() == "range":
            self.update_range_from_selection(self.text_page_listbox, self.text_pages_var)
        selected = self.text_page_listbox.curselection()
        if selected:
            idx = selected[0]
            file_path = self.text_in_file.get()
            if file_path and Path(file_path).exists():
                self.show_page_preview(file_path, idx + 1, self.text_preview_label)

    # ----- Удаление страниц -----
    def create_delete_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Удалить страницы")
        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill='both', expand=True)

        main_frame = ttk.Frame(frm)
        main_frame.pack(fill='both', expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        ttk.Label(left_frame, text="Исходный PDF:").pack(anchor='w')
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(fill='x', pady=2)
        self.delete_in_file = tk.StringVar()
        entry = ttk.Entry(file_frame, textvariable=self.delete_in_file, width=40)
        entry.pack(side='left', expand=True, fill='x')
        entry.drop_target_register(DND_FILES)
        entry.dnd_bind('<<Drop>>', self.delete_drop_handler)
        ttk.Button(file_frame, text="Обзор", command=self.delete_load_pdf).pack(side='left', padx=5)

        ttk.Label(left_frame, text="Страницы для удаления (диапазоны, например: 1-3,5,7-9):").pack(anchor='w', pady=(10, 0))
        self.delete_pages_var = tk.StringVar()
        ttk.Entry(left_frame, textvariable=self.delete_pages_var, width=40).pack(fill='x', pady=2)

        ttk.Button(left_frame, text="Удалить и сохранить...", command=self.delete_pages_action).pack(pady=10)

        right_frame = ttk.Frame(main_frame, padding=(10, 0, 0, 0))
        right_frame.pack(side='right', fill='both', expand=False)

        ttk.Label(right_frame, text="Страницы", font=('', 10, 'bold')).pack(anchor='w')
        self.delete_page_listbox = tk.Listbox(right_frame, height=12, width=10, selectmode=tk.EXTENDED)
        self.delete_page_listbox.pack(fill='both', expand=True, pady=2)
        self.delete_page_listbox.bind('<<ListboxSelect>>', self.delete_on_page_select)

        ttk.Label(right_frame, text="Предпросмотр", font=('', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        self.delete_preview_label = ttk.Label(right_frame, text="Выберите файл", anchor='center', justify='center')
        self.delete_preview_label.pack(pady=5, fill='both', expand=True)

    def delete_drop_handler(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.delete_in_file.set(files[0])
            self.delete_load_pdf()

    def delete_load_pdf(self):
        file_path = self.delete_in_file.get()
        if file_path:
            self.populate_page_list(file_path, self.delete_page_listbox, self.delete_preview_label)
            self.update_range_from_selection(self.delete_page_listbox, self.delete_pages_var)

    def delete_on_page_select(self, event):
        self.update_range_from_selection(self.delete_page_listbox, self.delete_pages_var)
        selected = self.delete_page_listbox.curselection()
        if selected:
            idx = selected[0]
            file_path = self.delete_in_file.get()
            if file_path and Path(file_path).exists():
                self.show_page_preview(file_path, idx + 1, self.delete_preview_label)

    # ----- Изображения -----
    def create_images_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Изображения")
        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill='both', expand=True)

        # Блок извлечения изображений
        extract_frame = ttk.LabelFrame(frm, text="Извлечь изображения из PDF", padding=5)
        extract_frame.pack(fill='x', pady=5)

        extract_main = ttk.Frame(extract_frame)
        extract_main.pack(fill='both', expand=True)

        left_extract = ttk.Frame(extract_main)
        left_extract.pack(side='left', fill='both', expand=True)

        ttk.Label(left_extract, text="Исходный PDF:").pack(anchor='w')
        file_frame = ttk.Frame(left_extract)
        file_frame.pack(fill='x', pady=2)
        self.img_extract_in_file = tk.StringVar()
        entry = ttk.Entry(file_frame, textvariable=self.img_extract_in_file, width=30)
        entry.pack(side='left', expand=True, fill='x')
        entry.drop_target_register(DND_FILES)
        entry.dnd_bind('<<Drop>>', self.img_extract_drop_handler)
        ttk.Button(file_frame, text="Обзор", command=self.img_extract_load_pdf).pack(side='left', padx=5)

        self.img_extract_scope_var = tk.StringVar(value="all")
        ttk.Radiobutton(left_extract, text="Все страницы", variable=self.img_extract_scope_var, value="all").pack(anchor='w')
        ttk.Radiobutton(left_extract, text="Только указанные", variable=self.img_extract_scope_var, value="range").pack(anchor='w')
        range_frame = ttk.Frame(left_extract)
        range_frame.pack(fill='x', pady=2)
        ttk.Label(range_frame, text="Диапазоны:").pack(side='left')
        self.img_extract_pages_var = tk.StringVar()
        ttk.Entry(range_frame, textvariable=self.img_extract_pages_var, width=20).pack(side='left', padx=5)

        ttk.Button(left_extract, text="Извлечь изображения...", command=self.extract_images_action).pack(pady=5)

        right_extract = ttk.Frame(extract_main, padding=(10, 0, 0, 0))
        right_extract.pack(side='right', fill='both', expand=False)

        ttk.Label(right_extract, text="Страницы", font=('', 10, 'bold')).pack(anchor='w')
        self.img_extract_page_listbox = tk.Listbox(right_extract, height=8, width=10, selectmode=tk.EXTENDED)
        self.img_extract_page_listbox.pack(fill='both', expand=True, pady=2)
        self.img_extract_page_listbox.bind('<<ListboxSelect>>', self.img_extract_on_page_select)

        ttk.Label(right_extract, text="Предпросмотр", font=('', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        self.img_extract_preview_label = ttk.Label(right_extract, text="Выберите файл", anchor='center', justify='center')
        self.img_extract_preview_label.pack(pady=5, fill='both', expand=True)

        # ----- Блок создания PDF из изображений -----
        create_frame = ttk.LabelFrame(frm, text="Создать PDF из изображений", padding=5)
        create_frame.pack(fill='both', expand=True, pady=5)

        top_btn_frame = ttk.Frame(create_frame)
        top_btn_frame.pack(fill='x', pady=2)
        ttk.Button(top_btn_frame, text="Добавить изображения", command=self.select_images_files).pack(side='left', padx=5)
        ttk.Button(top_btn_frame, text="Очистить список", command=lambda: self.img_create_list.delete(0, tk.END)).pack(side='left')
        ttk.Button(top_btn_frame, text="Удалить выбранное", command=self.img_remove_selected).pack(side='left', padx=5)

        list_frame = ttk.Frame(create_frame)
        list_frame.pack(fill='both', expand=True, pady=5)
        self.img_create_list = tk.Listbox(list_frame, height=6, selectmode=tk.EXTENDED)
        self.img_create_list.pack(side='left', fill='both', expand=True)
        self.img_create_list.drop_target_register(DND_FILES)
        self.img_create_list.dnd_bind('<<Drop>>', lambda e: self.on_drop_files_list(e, self.img_create_list))

        order_btn_frame = ttk.Frame(list_frame)
        order_btn_frame.pack(side='right', fill='y', padx=5)
        ttk.Button(order_btn_frame, text="▲ Вверх", command=self.img_move_up).pack(pady=2)
        ttk.Button(order_btn_frame, text="▼ Вниз", command=self.img_move_down).pack(pady=2)

        ttk.Button(create_frame, text="Создать PDF...", command=self.create_pdf_from_images_action).pack(pady=10)

    def img_extract_drop_handler(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.img_extract_in_file.set(files[0])
            self.img_extract_load_pdf()

    def img_extract_load_pdf(self):
        file_path = self.img_extract_in_file.get()
        if file_path:
            self.populate_page_list(file_path, self.img_extract_page_listbox, self.img_extract_preview_label)

    def img_extract_on_page_select(self, event):
        selected = self.img_extract_page_listbox.curselection()
        if selected:
            idx = selected[0]
            file_path = self.img_extract_in_file.get()
            if file_path and Path(file_path).exists():
                self.show_page_preview(file_path, idx + 1, self.img_extract_preview_label)


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    root.withdraw()  # скрываем главное окно до завершения загрузки

    # Показываем встроенный splash PyInstaller (если есть) — он уже висит,
    # здесь ничего создавать не нужно.

    app = PDFApp(root)

    # Закрываем splash от PyInstaller
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

    # Показываем главное окно
    root.deiconify()
    root.mainloop()