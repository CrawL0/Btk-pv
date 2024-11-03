import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import json
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading
import cv2
import numpy as np
from mutagen.mp3 import MP3
import requests
import subprocess
from datetime import datetime, timedelta
import math
import PyPDF2
import time
import shutil
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
import os

# .env dosyasını yükle
load_dotenv()

# API anahtarlarını al
genai_api_key = os.getenv("GENAI_API_KEY")
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

# API anahtarlarını sınıfta kullan


class ProcessingDialog:
    def __init__(self, parent, title="İşlem"):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x100")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center window
        self.center_window()
        
        # Processing message
        self.message_var = tk.StringVar()
        self.label = ttk.Label(
            self.dialog,
            textvariable=self.message_var,
            font=('Helvetica', 10),
            wraplength=250
        )
        self.label.pack(pady=20)
        
        # Keep dialog on top
        self.dialog.attributes('-topmost', True)
        
    def center_window(self):
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
    
    def update_message(self, message):
        self.message_var.set(message)
        self.dialog.update()
    
    def close(self):
        self.dialog.grab_release()
        self.dialog.destroy()
        
        
class PDFAnalyzerFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.setup_ui()
    
    
    def create_project_folder(self, pdf_content):
        """PDF içeriğinden proje klasörü oluştur"""
        try:
            # İlk sayfanın ilk birkaç satırını başlık olarak kullan
            title_lines = pdf_content.split('\n')[:3]  # İlk 3 satır
            project_title = ' '.join(line.strip() for line in title_lines if line.strip())[:100]
            
            # Başlığı klasör adına uygun hale getir
            folder_name = "".join(x for x in project_title if x.isalnum() or x in (" ", "-", "_"))
            folder_name = folder_name.replace(" ", "_")[:50]  # Uzunluğu sınırla
            
            # Tarih ekle (benzersiz olması için)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_folder = f"{folder_name}_{timestamp}"
            
            # Ana proje klasörünü oluştur
            os.makedirs("projects", exist_ok=True)
            full_project_path = os.path.join("projects", project_folder)
            os.makedirs(full_project_path, exist_ok=True)
            
            # Alt klasörleri oluştur
            folders = [
                'pdf_analizi',
                'prompt_ciktisi',
                'gorseller',
                'video_dosyalari',
                'video_dosyalari/sesler',
                'final_video'
            ]
            
            for folder in folders:
                os.makedirs(os.path.join(full_project_path, folder), exist_ok=True)
            
            return full_project_path
            
        except Exception as e:
            messagebox.showerror("Hata", f"Proje klasörü oluşturma hatası: {str(e)}")
            return None
    
    
    
    
    def setup_ui(self):
        # Frame başlığı
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            header_frame,
            text="PDF Analizi",
            font=('Helvetica', 12, 'bold')
        ).pack(side=tk.LEFT)
    
        # Sol panel - PDF içeriği
        left_panel = ttk.LabelFrame(self, text="PDF İçeriği", padding="10")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    
        self.content_text = scrolledtext.ScrolledText(
            left_panel,
            wrap=tk.WORD,
            width=40,
            height=25
        )
        self.content_text.pack(fill=tk.BOTH, expand=True)
    
        # Sağ panel - Analiz sonuçları
        right_panel = ttk.LabelFrame(self, text="Analiz Sonuçları", padding="10")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
        self.analysis_text = scrolledtext.ScrolledText(
            right_panel,
            wrap=tk.WORD,
            width=40,
            height=25
        )
        self.analysis_text.pack(fill=tk.BOTH, expand=True)
    
        # Kontrol butonları
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, pady=10)
    
        self.analyze_button = ttk.Button(
            button_frame,
            text="PDF'yi Analiz Et",
            command=self.analyze_pdf,
            state=tk.DISABLED  # Başlangıçta devre dışı
        )
        self.analyze_button.pack(side=tk.LEFT, padx=5)

    def load_pdf_content(self, pdf_path):
        """PDF içeriğini yükle ve metin kontrolü yap"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        
                # Metin içeriği kontrolü
                if not text.strip() or len(text.strip()) < 50:
                    messagebox.showerror(
                        "Hata", 
                        "PDF dosyası yeterli metin içermiyor veya sadece görsel içeriyor.\n"
                        "Lütfen metin içeren başka bir PDF dosyası seçin."
                    )
                    self.content_text.delete(1.0, tk.END)
                    self.analyze_button.configure(state=tk.DISABLED)
                    return None
        
                # Proje klasörü oluştur ve controller'a aktar
                project_folder = self.create_project_folder(text)
                if project_folder:
                    self.controller.project_folder = project_folder
        
                self.content_text.delete(1.0, tk.END)
                self.content_text.insert(tk.END, text)
                self.analyze_button.configure(state=tk.NORMAL)
                return text
                    
        except Exception as e:
                messagebox.showerror("Hata", f"PDF yüklenirken hata oluştu: {str(e)}")
                self.analyze_button.configure(state=tk.DISABLED)
                return None

    def analyze_pdf(self):
        """PDF'yi analiz et ve Gemini API ile özet çıkar"""
        try:
            pdf_content = self.content_text.get(1.0, tk.END.strip())
            if not pdf_content:
                messagebox.showerror("Hata", "PDF içeriği bulunamadı!")
                return
    
            # Show processing dialog
            processing = ProcessingDialog(self.winfo_toplevel(), "PDF Analizi")
            processing.update_message("PDF analiz ediliyor...")
    
            analysis_prompt = f"""
            Aşağıdaki PDF içeriğini analiz et ve şu başlıklar altında özetle (detaya gir):
    
            1. Ana Konular
            2. Önemli Noktalar
            3. Önerilen Konu Başlıkları (4 başlık öner)
            4. Hedef Kitle Önerisi
            5. İçerik Tonu Önerisi
    
            PDF İçeriği:
            {pdf_content[:]}
            """
    
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content(analysis_prompt)
    
            # Analiz sonuçlarını hem metin kutusuna hem de dosyaya kaydet
            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(tk.END, response.text)
    
            # Analiz sonuçlarını dosyaya kaydet
            if hasattr(self.controller, 'project_folder'):
                analysis_path = os.path.join(
                    self.controller.project_folder,
                    'pdf_analizi',
                    'analiz_sonuclari.txt'
                )
                with open(analysis_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
    
            # Controller'a analiz sonucunu aktar
            self.controller.pdf_analysis = response.text
    
            processing.close()
            messagebox.showinfo("Başarılı", "PDF analizi tamamlandı!")
    
        except Exception as e:
            if 'processing' in locals():
                processing.close()
            messagebox.showerror("Hata", f"Analiz sırasında hata oluştu: {str(e)}")

class VideoGenerator:
    def __init__(self, output_dir, generation_data):
        self.output_dir = output_dir
        self.generation_data = generation_data
        self.height = 1920
        self.width = 1080
        self.fps = 30

    def create_base_frame(self):
        """Temel frame oluştur"""
        return np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def add_text_to_frame(self, frame, text, y_position, font_size=60, color=(255, 255, 255)):
        """Frame'e text ekle"""
        img_pil = Image.fromarray(frame)
        draw = ImageDraw.Draw(img_pil)
        
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Text wrap
        words = text.split()
        lines = []
        current_line = []
        max_width = self.width - 100  # Margins
        
        for word in words:
            current_line.append(word)
            line = ' '.join(current_line)
            line_width = draw.textlength(line, font=font)
            if line_width > max_width:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        
        y = y_position
        for line in lines:
            text_width = draw.textlength(line, font=font)
            x = (self.width - text_width) / 2
            draw.text((x, y), line, font=font, fill=color)
            y += font_size * 1.5
            
        return np.array(img_pil)

    def add_text_overlay(self, frame, text, pos_y, font_size=40):
        """Yarı saydam arkaplan üzerine text ekle"""
        overlay = frame.copy()
        overlay_height = 200
        cv2.rectangle(overlay, 
                     (0, pos_y), 
                     (self.width, pos_y + overlay_height),
                     (0, 0, 0), 
                     -1)
        
        alpha = 0.7
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        return self.add_text_to_frame(frame, text, pos_y + 20, font_size)

    def get_audio_duration(self, audio_path):
        """MP3 dosyasının süresini al"""
        try:
            audio = MP3(audio_path)
            return audio.info.length
        except Exception as e:
            print(f"Ses süresi alınamadı: {str(e)}")
            return 5.0  # Varsayılan süre

    def create_title_overlay(self, image, title):
        """İlk görsele başlık ekle"""
        overlay_height = 200
        overlay = image.copy()
        
        # Üst kısma yarı saydam siyah overlay ekle
        cv2.rectangle(overlay, 
                     (0, 0),
                     (self.width, overlay_height),
                     (0, 0, 0),
                     -1)
        
        # Blend the overlay
        alpha = 0.7
        image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)
        
        # Başlığı ekle
        return self.add_text_to_frame(image, title, 50, 60)

    def generate_video(self):
        try:
            if not self.generation_data or 'title' not in self.generation_data:
                raise Exception("Video başlığı bulunamadı")
                
            if not self.generation_data.get('images'):
                raise Exception("Görsel dosyaları bulunamadı")
                
            if not self.generation_data.get('texts'):
                raise Exception("Metin içeriği bulunamadı")
            
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Get project title and clean it
            title = str(self.generation_data['title'])
            clean_title = "".join(x for x in title if x.isalnum() or x in (" ", "-", "_"))
            clean_title = clean_title.replace(" ", "_")[:50]
            
            if not clean_title:
                clean_title = "video"
            
            # Ses dosyalarının yolları
            ses_klasoru = os.path.join(self.output_dir, "sesler")
            ana_baslik_ses = os.path.join(ses_klasoru, "0_ana_baslik.mp3")
            
            # Video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            temp_video_path = os.path.join(self.output_dir, f'temp_{clean_title}.mp4')
            
            out = cv2.VideoWriter(
                temp_video_path,
                fourcc,
                self.fps,
                (self.width, self.height)
            )
            
            if not out.isOpened():
                raise Exception("Video writer açılamadı")

            # Başlık süresi
            title_duration = self.get_audio_duration(ana_baslik_ses)
            
            # İlk görsel üzerine başlık ekle
            first_image = cv2.imread(self.generation_data['images'][0])
            first_image = cv2.resize(first_image, (self.width, self.height))
            titled_first_image = self.create_title_overlay(first_image, self.generation_data['title'])
            
            # Başlık süresince frame'leri yaz
            for _ in range(int(title_duration * self.fps)):
                out.write(titled_first_image)
            
            # Diğer bölümler için
            for i in range(4):
                # Ses süresini al
                audio_path = os.path.join(ses_klasoru, f"{i+1}_metin.mp3")
                section_duration = self.get_audio_duration(audio_path)
                
                # Görseli hazırla
                image = cv2.imread(self.generation_data['images'][i])
                image = cv2.resize(image, (self.width, self.height))
                
                # Text overlay ekle
                frame_with_text = self.add_text_overlay(
                    image,
                    self.generation_data['texts'][i],
                    self.height - 250
                )
                
                # Ses süresi kadar frame ekle
                for _ in range(int(section_duration * self.fps)):
                    out.write(frame_with_text)
            
            out.release()
            
            # Sesleri birleştir
            audio_files = [ana_baslik_ses]
            for i in range(1, 5):
                audio_files.append(os.path.join(ses_klasoru, f"{i}_metin.mp3"))
            
            # Ses listesi dosyası
            concat_list = os.path.join(self.output_dir, "concat_list.txt")
            with open(concat_list, "w") as f:
                for audio_file in audio_files:
                    f.write(f"file '{audio_file}'\n")
            
            # Sesleri birleştir
            combined_audio = os.path.join(self.output_dir, "combined_audio.mp3")
            subprocess.call([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_list,
                '-c', 'copy', combined_audio
            ])
            
            # Final video oluştur
            final_video_path = os.path.join(self.output_dir, f'{clean_title}.mp4')
            subprocess.call([
                'ffmpeg', '-y',
                '-i', temp_video_path,
                '-i', combined_audio,
                '-c:v', 'copy',
                '-c:a', 'aac',
                final_video_path
            ])
            
            # Geçici dosyaları temizle
            os.remove(temp_video_path)
            os.remove(combined_audio)
            os.remove(concat_list)
            
            return final_video_path
            
        except Exception as e:
            print(f"Video generation error details: {str(e)}")
            raise Exception(f"Video generation error: {str(e)}")
class InteractiveReelsGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive Reels Generator")
        self.root.geometry("1400x800")

        genai.configure(api_key=genai_api_key)
        self.ELEVENLABS_API_KEY = elevenlabs_api_key
        self.OPENAI_API_KEY = openai_api_key
        
        # Variables
        self.pdf_path = None
        self.current_step = 1
        self.total_steps = 5
        self.pdf_analysis = None
        self.generation_data = {
            'prompt': '',
            'output': '',
            'image_prompts': [],
            'images': []
        }
        self.current_image_index = 0
        
        # Create frames
        self.setup_ui()
        self.project_folder = None
        
    def setup_ui(self):
        # Main container
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Step indicator
        self.step_frame = ttk.Frame(self.main_frame)
        self.step_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.step_label = ttk.Label(
            self.step_frame, 
            text="Adım 1/5: PDF Seçimi", 
            font=('Helvetica', 12, 'bold')
        )
        self.step_label.pack(side=tk.LEFT)
        
        # Content frame
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create all frames
        self.pdf_frame = self.create_pdf_frame()
        self.pdf_analyzer_frame = PDFAnalyzerFrame(self.content_frame, self)
        self.prompt_frame = self.create_prompt_frame()
        self.output_frame = self.create_output_frame()
        self.image_frame = self.create_image_frame()
        
        # Navigation
        self.nav_frame = ttk.Frame(self.main_frame)
        self.nav_frame.pack(fill=tk.X, pady=10)
        
        self.prev_button = ttk.Button(
            self.nav_frame,
            text="Geri",
            command=self.previous_step,
            state=tk.DISABLED
        )
        self.prev_button.pack(side=tk.LEFT)
        
        self.next_button = ttk.Button(
            self.nav_frame,
            text="İleri",
            command=self.next_step
        )
        self.next_button.pack(side=tk.RIGHT)
        
        # Show initial step
        self.show_current_step()
        
    def create_pdf_frame(self):
        frame = ttk.Frame(self.content_frame)
        
        select_frame = ttk.LabelFrame(frame, text="PDF Dosyası Seç", padding="10")
        select_frame.pack(fill=tk.X, pady=10)
        
        self.pdf_path_var = tk.StringVar()
        pdf_entry = ttk.Entry(select_frame, textvariable=self.pdf_path_var, width=50)
        pdf_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_button = ttk.Button(
            select_frame,
            text="Gözat",
            command=self.browse_pdf
        )
        browse_button.pack(side=tk.RIGHT)
        
        return frame

    def create_prompt_frame(self):
        frame = ttk.Frame(self.content_frame)
        
        # Style selection
        style_frame = ttk.LabelFrame(frame, text="Anlatım Tarzı", padding="10")
        style_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Add text entry for custom style
        style_entry_frame = ttk.Frame(style_frame)
        style_entry_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(style_entry_frame, text="Özel Anlatım Tarzı:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.style_text = tk.StringVar()
        self.style_text.trace_add("write", self.on_style_text_change)  # Add trace
        
        style_entry = ttk.Entry(style_entry_frame, textvariable=self.style_text, width=50)
        style_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Example styles
        example_frame = ttk.LabelFrame(style_frame, text="Örnek Tarzlar", padding="5")
        example_frame.pack(fill=tk.X, pady=5)
        
        example_styles = [
            "Ortaokul öğrencisi düzeyinde anlat",
            "Lise detaylı bir şekilde anlat",
            "Anaokul düzeyinde anlat",
            "Eğlenceli bir şekilde anlat"
        ]
        
        for style in example_styles:
            ttk.Button(
                example_frame,
                text=style,
                command=lambda s=style: self.style_text.set(s)
            ).pack(side=tk.LEFT, padx=5)
        
        # Prompt edit
        prompt_frame = ttk.LabelFrame(frame, text="Prompt Önizleme ve Düzenleme", padding="10")
        prompt_frame.pack(fill=tk.BOTH, expand=True)
        
        self.prompt_text = scrolledtext.ScrolledText(
            prompt_frame,
            wrap=tk.WORD,
            width=60,
            height=20
        )
        self.prompt_text.pack(fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(prompt_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Prompt Oluştur",
            command=self.apply_prompt_changes
        ).pack(side=tk.LEFT, padx=5)
        
        return frame
    
    def on_style_text_change(self, *args):
        """Style text değiştiğinde promptu güncelle"""
        if not self.pdf_path or not self.pdf_analysis:
            return
            
        try:
            template = {
                "reels_başlık": "Ana Başlık Buraya",
                "içerik": {
                    "bölüm1": {
                        "text1_başlık": "Birinci Bölüm Başlığı",
                        "text1": "Birinci bölüm metni",
                        "image_prompt1": "Birinci görsel promptu"
                    },
                    "bölüm2": {
                        "text2_başlık": "İkinci Bölüm Başlığı",
                        "text2": "İkinci bölüm metni",
                        "image_prompt2": "İkinci görsel promptu"
                    },
                    "bölüm3": {
                        "text3_başlık": "Üçüncü Bölüm Başlığı",
                        "text3": "Üçüncü bölüm metni",
                        "image_prompt3": "Üçüncü görsel promptu"
                    },
                    "bölüm4": {
                        "text4_başlık": "Dördüncü Bölüm Başlığı",
                        "text4": "Dördüncü bölüm metni",
                        "image_prompt4": "Dördüncü görsel promptu"
                    }
                }
            }
    
            prompt = f"""
            PDF Analiz Sonuçları:
            {self.pdf_analysis}
    
            Yukarıdaki analiz sonuçlarını kullanarak ve aşağıdaki anlatım tarzında bir metin oluştur:
    
            Anlatım Tarzı:
            {self.style_text.get()}
            
            Text formatı:
            {json.dumps(template, indent=2, ensure_ascii=False)}
            """
    
            self.generation_data['prompt'] = prompt
            self.prompt_text.delete(1.0, tk.END)
            self.prompt_text.insert(tk.END, prompt)
    
        except Exception as e:
            print(f"Prompt güncelleme hatası: {str(e)}")
    
    def process_texts_to_audio(self, json_data, output_dir):
        """Metinleri sese çevirme"""
        try:
            ses_klasoru = os.path.join(output_dir, "sesler")
            os.makedirs(ses_klasoru, exist_ok=True)
    
            # Ana başlık sesi
            ana_baslik_dosya = os.path.join(ses_klasoru, "0_ana_baslik.mp3")
            if self.create_audio_file(json_data['title'], ana_baslik_dosya):
                print("Ana başlık sesi oluşturuldu")
    
            # Diğer metinlerin sesleri
            for i, text in enumerate(json_data['texts'], 1):
                filename = os.path.join(ses_klasoru, f"{i}_metin.mp3")
                if self.create_audio_file(text, filename):
                    print(f"Ses dosyası oluşturuldu: {i}_metin.mp3")
                time.sleep(1)  # API rate limiting
    
        except Exception as e:
            raise Exception(f"Ses oluşturma hatası: {str(e)}")

    def create_audio_file(self, text, filename):
        """Eleven Labs API ile ses dosyası oluştur"""
        url = "https://api.elevenlabs.io/v1/text-to-speech/KbaseEXyT9EE0CQLEfbB"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.ELEVENLABS_API_KEY
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
    
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
    
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"Ses dosyası oluşturma hatası: {str(e)}")
            return False


    def create_output_frame(self):
        frame = ttk.Frame(self.content_frame)
        
        output_frame = ttk.LabelFrame(frame, text="Gemini Çıktısı ve Düzenleme", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            width=60,
            height=20
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(output_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="JSON Formatla",
            command=self.format_json
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Görselleri Oluştur",
            command=self.apply_output_changes
        ).pack(side=tk.LEFT, padx=5)
        
        return frame

    def create_image_frame(self):
        frame = ttk.Frame(self.content_frame)
        
        # Image preview
        preview_frame = ttk.LabelFrame(frame, text="Görsel Önizleme ve Düzenleme", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(preview_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(preview_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.image_label = ttk.Label(left_frame)
        self.image_label.pack(pady=10)
        
        nav_frame = ttk.Frame(left_frame)
        nav_frame.pack(fill=tk.X)
        
        self.prev_img_button = ttk.Button(
            nav_frame,
            text="←",
            command=self.previous_image,
            width=3
        )
        self.prev_img_button.pack(side=tk.LEFT, padx=5)
        
        self.image_counter = ttk.Label(nav_frame, text="1/4")
        self.image_counter.pack(side=tk.LEFT, expand=True)
        
        self.next_img_button = ttk.Button(
            nav_frame,
            text="→",
            command=self.next_image,
            width=3
        )
        self.next_img_button.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(right_frame, text="Görsel Promptu:").pack(anchor=tk.W, pady=(0, 5))
        
        self.image_prompt_text = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            width=40,
            height=10
        )
        self.image_prompt_text.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(
            right_frame,
            text="Görseli Yeniden Oluştur",
            command=self.regenerate_current_image
        ).pack(pady=10)
        
        return frame

    def show_current_step(self):
        # Hide all frames
        for frame in [self.pdf_frame, self.pdf_analyzer_frame, 
                     self.prompt_frame, self.output_frame, self.image_frame]:
            frame.pack_forget()

        # Show current frame
        if self.current_step == 1:
            self.step_label.configure(text="Adım 1/5: PDF Seçimi")
            self.pdf_frame.pack(fill=tk.BOTH, expand=True)
        elif self.current_step == 2:
            self.step_label.configure(text="Adım 2/5: PDF Analizi")
            self.pdf_analyzer_frame.pack(fill=tk.BOTH, expand=True)
            if self.pdf_path:
                self.pdf_analyzer_frame.load_pdf_content(self.pdf_path)
        elif self.current_step == 3:
            self.step_label.configure(text="Adım 3/5: Prompt Düzenleme")
            self.prompt_frame.pack(fill=tk.BOTH, expand=True)
        elif self.current_step == 4:
            self.step_label.configure(text="Adım 4/5: Çıktı Düzenleme")
            self.output_frame.pack(fill=tk.BOTH, expand=True)
        elif self.current_step == 5:
            self.step_label.configure(text="Adım 5/5: Görselleri Düzenleme")
            self.image_frame.pack(fill=tk.BOTH, expand=True)

        # Update navigation buttons
        self.prev_button.configure(state=tk.NORMAL if self.current_step > 1 else tk.DISABLED)
        self.next_button.configure(text="Bitir" if self.current_step == self.total_steps else "İleri")

    def browse_pdf(self):
        filepath = filedialog.askopenfilename(
            title="PDF Dosyası Seç",
            filetypes=[("PDF Dosyaları", "*.pdf")]
        )
        if filepath:
            self.pdf_path = filepath
            self.pdf_path_var.set(filepath)

    def generate_prompt(self):
        if not self.pdf_path or not self.pdf_analysis:
            messagebox.showerror("Hata", "Önce PDF analizi yapmalısınız!")
            return

        try:
            style_texts = {
                "çarpıcı": "çarpıcı sözlerle başlıkları anlat",
                "detaylı": "konuyu detaylı bir şekilde anlat",
                "öğretici": "öğrencilerin anlayabileceği şekilde anlat",
                "eğlenceli": "eğlenceli bir şekilde anlat"
            }

            template = {
                "reels_başlık": "Ana Başlık Buraya",
                "içerik": {
                    "bölüm1": {
                        "text1_başlık": "Birinci Bölüm Başlığı",
                        "text1": "Birinci bölüm metni",
                        "image_prompt1": "Birinci görsel promptu"
                    },
                    "bölüm2": {
                        "text2_başlık": "İkinci Bölüm Başlığı",
                        "text2": "İkinci bölüm metni",
                        "image_prompt2": "İkinci görsel promptu"
                    },
                    "bölüm3": {
                        "text3_başlık": "Üçüncü Bölüm Başlığı",
                        "text3": "Üçüncü bölüm metni",
                        "image_prompt3": "Üçüncü görsel promptu"
                    },
                    "bölüm4": {
                        "text4_başlık": "Dördüncü Bölüm Başlığı",
                        "text4": "Dördüncü bölüm metni",
                        "image_prompt4": "Dördüncü görsel promptu"
                    }
                }
            }

            prompt = f"""
            PDF Analiz Sonuçları:
            {self.pdf_analysis}

            Yukarıdaki analiz sonuçlarını kullanarak ve aşağıdaki anlatım tarzında bir metin oluştur:

            Anlatım Tarzı:
            {style_texts[self.style_var.get()]}
            
            Text formatı:
            {json.dumps(template, indent=2, ensure_ascii=False)}
            """

            self.generation_data['prompt'] = prompt
            self.prompt_text.delete(1.0, tk.END)
            self.prompt_text.insert(tk.END, prompt)

        except Exception as e:
            messagebox.showerror("Hata", f"Prompt oluşturulurken hata: {str(e)}")

    def apply_prompt_changes(self):
        try:
            prompt = self.prompt_text.get(1.0, tk.END.strip())
            self.generation_data['prompt'] = prompt
            
            processing = ProcessingDialog(self.root, "Prompt İşleniyor")
            processing.update_message("Prompt işleniyor ve çıktı oluşturuluyor...")
            
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content(prompt)
            
            # Çıktıyı JSON formatına dönüştür
            response_text = response.text.replace("```json", "").replace("```", "").strip()
            try:
                json_data = json.loads(response_text)
            except json.JSONDecodeError:
                raise Exception("Gemini çıktısı JSON formatında değil. Lütfen çıktıyı düzenleyip tekrar deneyin.")
            
            # JSON dosyasını kaydet
            if self.project_folder:
                prompt_output_path = os.path.join(self.project_folder, "prompt_ciktisi", "output.json")
                with open(prompt_output_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            self.generation_data['output'] = response_text
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, response_text)
            
            processing.close()
            messagebox.showinfo("Başarılı", "Prompt işlendi ve çıktı oluşturuldu!")
            
        except Exception as e:
            processing.close()
            messagebox.showerror("Hata", f"Prompt işlenirken hata: {str(e)}")

    def format_json(self):
        try:
            current_text = self.output_text.get(1.0, tk.END.strip())
            current_text = current_text.replace("```json", "").replace("```", "").strip()
            
            json_obj = json.loads(current_text)
            formatted_json = json.dumps(json_obj, indent=2, ensure_ascii=False)
            
            # JSON'ı dosyaya kaydet
            if self.project_folder:
                prompt_output_path = os.path.join(self.project_folder, "prompt_ciktisi", "output.json")
                with open(prompt_output_path, 'w', encoding='utf-8') as f:
                    json.dump(json_obj, f, ensure_ascii=False, indent=2)
            
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, formatted_json)
            
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Hata", f"Geçersiz JSON formatı: {str(e)}")

    def apply_output_changes(self):
        try:
            # Önce çıktının JSON formatında olduğundan emin ol
            output = self.output_text.get(1.0, tk.END.strip())
            json_data = json.loads(output)
            
            # JSON dosyasını kaydet
            if self.project_folder:
                output_path = os.path.join(self.project_folder, "prompt_ciktisi", "output.json")
                with open(output_path, "w", encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            # Image prompts'ları ayıkla
            self.generation_data['image_prompts'] = [
                json_data['içerik'][f'bölüm{i}'][f'image_prompt{i}']
                for i in range(1, 5)
            ]
            
            # Görselleri oluştur
            if messagebox.askyesno("Onay", "Görseller oluşturulacak. Bu işlem biraz zaman alabilir. Devam etmek istiyor musunuz?"):
                self.generate_all_images_with_progress()
                
        except json.JSONDecodeError:
            messagebox.showerror("Hata", "Geçersiz JSON formatı!")
        except KeyError as e:
            messagebox.showerror("Hata", f"JSON formatında gerekli alan bulunamadı: {str(e)}")
        except Exception as e:
            messagebox.showerror("Hata", f"Çıktı işlenirken hata: {str(e)}")

    def generate_all_images_with_progress(self):
        try:
            client = OpenAI(api_key=self.OPENAI_API_KEY)
            self.generation_data['images'] = []
            
            # Show processing dialog
            processing = ProcessingDialog(self.root, "Görseller Oluşturuluyor")
            
            for i, prompt in enumerate(self.generation_data['image_prompts'], 1):
                processing.update_message(f"{i}/4 görsel oluşturuluyor...")
                
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                    quality="standard",
                    response_format="url"
                )
                
                image_url = response.data[0].url
                image_response = requests.get(image_url)
                image_response.raise_for_status()
                
                os.makedirs("output/images", exist_ok=True)
                image_path = os.path.join("output/images", f"image_{i}.png")
                
                with open(image_path, 'wb') as f:
                    f.write(image_response.content)
                
                self.generation_data['images'].append(image_path)
            
            processing.close()
            self.current_image_index = 0
            self.update_image_display()
            messagebox.showinfo("Başarılı", "Tüm görseller oluşturuldu!")
            
        except Exception as e:
            if 'processing' in locals():
                processing.close()
            messagebox.showerror("Hata", f"Görsel oluşturma hatası: {str(e)}")

    def update_image_display(self):
        if not self.generation_data['images']:
            return
            
        image_path = self.generation_data['images'][self.current_image_index]
        image = Image.open(image_path)
        image.thumbnail((400, 400))
        photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=photo)
        self.image_label.image = photo
        
        self.image_prompt_text.delete(1.0, tk.END)
        self.image_prompt_text.insert(tk.END, 
            self.generation_data['image_prompts'][self.current_image_index])
        
        self.image_counter.configure(
            text=f"{self.current_image_index + 1}/{len(self.generation_data['images'])}")
        
        self.prev_img_button.configure(
            state=tk.NORMAL if self.current_image_index > 0 else tk.DISABLED)
        self.next_img_button.configure(
            state=tk.NORMAL if self.current_image_index < len(self.generation_data['images'])-1 else tk.DISABLED)

    def previous_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.update_image_display()

    def next_image(self):
        if self.current_image_index < len(self.generation_data['images']) - 1:
            self.current_image_index += 1
            self.update_image_display()

    def regenerate_current_image(self):
        try:
            new_prompt = self.image_prompt_text.get(1.0, tk.END.strip())
            self.generation_data['image_prompts'][self.current_image_index] = new_prompt
            
            client = OpenAI(api_key=self.OPENAI_API_KEY)
            response = client.images.generate(
                model="dall-e-3",
                prompt=new_prompt,
                n=1,
                size="1024x1024",
                quality="standard",
                response_format="url"
            )
            
            image_url = response.data[0].url
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            
            image_path = self.generation_data['images'][self.current_image_index]
            with open(image_path, 'wb') as f:
                f.write(image_response.content)
            
            self.update_image_display()
            messagebox.showinfo("Başarılı", "Görsel yeniden oluşturuldu!")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Görsel yeniden oluşturma hatası: {str(e)}")

    def previous_step(self):
        if self.current_step > 1:
            self.current_step -= 1
            self.show_current_step()

    def next_step(self):
        if self.current_step < self.total_steps:
            if self.validate_current_step():
                self.current_step += 1
                self.show_current_step()
        else:
            self.finish_generation()

    def validate_current_step(self):
        if self.current_step == 1 and not self.pdf_path:
            messagebox.showerror("Hata", "Lütfen bir PDF dosyası seçin!")
            return False
        elif self.current_step == 2 and not self.pdf_analysis:
            messagebox.showerror("Hata", "Lütfen önce PDF'yi analiz edin!")
            return False
        elif self.current_step == 3 and not self.generation_data['prompt']:
            messagebox.showerror("Hata", "Lütfen önce prompt oluşturun!")
            return False
        elif self.current_step == 4 and not self.generation_data['output']:
            messagebox.showerror("Hata", "Lütfen çıktıyı oluşturun!")
            return False
        # Görsel oluşturma kontrolü
        elif self.current_step == 4 and self.next_button.cget('text') == "İleri":
            # Eğer görseller oluşturulmadıysa ve kullanıcı 5. adıma geçmeye çalışıyorsa
            if not self.generation_data.get('images'):
                messagebox.showerror("Hata", "Lütfen önce görselleri oluşturun!")
                return False
        return True


    def finish_generation(self):
        if messagebox.askyesno("Onay", "Video oluşturma işlemi başlatılsın mı?"):
            try:
                if not self.project_folder:
                    raise Exception("Proje klasörü bulunamadı")
                    
                output_path = os.path.join(self.project_folder, "prompt_ciktisi", "output.json")
                if not os.path.exists(output_path):
                    raise Exception("Output JSON dosyası bulunamadı")
                
                with open(output_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                if not json_data.get('reels_başlık'):
                    raise Exception("Video başlığı bulunamadı")
                
                processing = ProcessingDialog(self.root, "Video Oluşturuluyor")
                
                video_data = {
                    'title': json_data['reels_başlık'],
                    'images': self.generation_data['images'],
                    'texts': [
                        f"{json_data['içerik'][f'bölüm{i}'][f'text{i}_başlık']}: "
                        f"{json_data['içerik'][f'bölüm{i}'][f'text{i}']}"
                        for i in range(1, 5)
                    ]
                }
    
                # Gerekli klasörleri oluştur
                video_dosyalari = os.path.join(self.project_folder, "video_dosyalari")
                os.makedirs(video_dosyalari, exist_ok=True)
                
                ses_klasoru = os.path.join(video_dosyalari, "sesler")
                os.makedirs(ses_klasoru, exist_ok=True)
    
                # Ana başlık sesi
                processing.update_message("Ana başlık sesi oluşturuluyor...")
                ana_baslik_dosya = os.path.join(ses_klasoru, "0_ana_baslik.mp3")
                if not self.create_audio_file(video_data['title'], ana_baslik_dosya):
                    raise Exception("Ana başlık sesi oluşturulamadı")
    
                # Diğer metinlerin sesleri
                for i, text in enumerate(video_data['texts'], 1):
                    processing.update_message(f"{i}/4 ses dosyası oluşturuluyor...")
                    filename = os.path.join(ses_klasoru, f"{i}_metin.mp3")
                    if not self.create_audio_file(text, filename):
                        raise Exception(f"{i}. metin sesi oluşturulamadı")
                    time.sleep(1)
    
                # Video oluşturma
                processing.update_message("Video oluşturuluyor...")
                video_gen = VideoGenerator(video_dosyalari, video_data)
                video_path = video_gen.generate_video()
                
                if not video_path or not os.path.exists(video_path):
                    raise Exception("Video dosyası oluşturulamadı")
    
                # Final video klasörüne kopyala
                clean_title = "".join(x for x in video_data['title'] if x.isalnum() or x in (" ", "-", "_"))
                clean_title = clean_title.replace(" ", "_")[:50] or "video"
                final_video_path = os.path.join(self.project_folder, "final_video", f"{clean_title}.mp4")
                
                os.makedirs(os.path.dirname(final_video_path), exist_ok=True)
                shutil.copy2(video_path, final_video_path)
    
                processing.close()
                messagebox.showinfo("Başarılı", f"Video oluşturuldu!\nKonum: {final_video_path}")
    
            except Exception as e:
                if 'processing' in locals():
                    processing.close()
                messagebox.showerror("Hata", f"Video oluşturma hatası: {str(e)}")
    
    def combine_audio_video(self, video_path):
        """Ses ve videoyu birleştir"""
        output_dir = os.path.dirname(video_path)
        ses_klasoru = os.path.join(output_dir, "sesler")
        
        # Concat listesi oluştur
        concat_list = os.path.join(output_dir, "concat_list.txt")
        with open(concat_list, "w") as f:
            ses_dosyalari = sorted(
                [f for f in os.listdir(ses_klasoru) if f.endswith('.mp3')],
                key=lambda x: int(''.join(filter(str.isdigit, x.split('_')[0])))
            )
            for ses_dosya in ses_dosyalari:
                f.write(f"file '{os.path.join(ses_klasoru, ses_dosya)}'\n")
        
        # Sesleri birleştir
        combined_audio = os.path.join(output_dir, "combined_audio.mp3")
        subprocess.call([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_list,
            '-c', 'copy', combined_audio
        ])
        
        # Video ve sesi birleştir
        final_video = os.path.join(output_dir, "final_reels.mp4")
        subprocess.call([
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', combined_audio,
            '-c:v', 'copy', '-c:a', 'aac',
            final_video
        ])
        
        # Geçici dosyaları temizle
        os.remove(video_path)
        os.remove(combined_audio)
        os.remove(concat_list)

# VideoGenerator sınıfındaki create_title_sequence metodunu da güncelleyelim
    def create_title_sequence(self, title, duration):
        """Başlık sekansı oluştur"""
        n_frames = int(duration * self.fps)
        frames = []
        
        # Siyah arkaplan oluştur
        base_frame = self.create_base_frame()
        
        # Başlığı ekle
        img_pil = Image.fromarray(base_frame)
        draw = ImageDraw.Draw(img_pil)
        
        try:
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            font = ImageFont.load_default()
        
        # Text wrap uygula
        words = title.split()
        lines = []
        current_line = []
        max_width = self.width - 100  # Margins
        
        for word in words:
            current_line.append(word)
            line = ' '.join(current_line)
            line_width = draw.textlength(line, font=font)
            if line_width > max_width:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        
        # Başlığı ortala
        y = (self.height - (len(lines) * 80)) // 2  # 80 piksel line spacing
        for line in lines:
            text_width = draw.textlength(line, font=font)
            x = (self.width - text_width) // 2
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
            y += 80
        
        frame_with_text = np.array(img_pil)
        
        # Frameleri oluştur
        for _ in range(n_frames):
            frames.append(frame_with_text.copy())
            
        return frames

def main():
    root = tk.Tk()
    root.state('zoomed')
    app = InteractiveReelsGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()










