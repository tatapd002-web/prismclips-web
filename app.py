import streamlit as st
import cv2
import os
import subprocess
import whisper
import yt_dlp
import mediapipe as mp
from moviepy.editor import VideoFileClip

# ==========================================
# KONFIGURASI TAMPILAN WEB
# ==========================================
st.set_page_config(page_title="PRISMCLIPS Web App", page_icon="🎬", layout="centered")

st.title("🎬 PRISMCLIPS")
st.markdown("**Mesin Pembuat Video Pendek Otomatis (Manual Bypass Mode)**")
st.markdown("---")

# ==========================================
# FUNGSI MESIN INTI (Sama seperti sebelumnya)
# ==========================================
def unduh_youtube(url_youtube, nama_file="youtube_mentah.mp4"):
    opsi = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': nama_file, 'quiet': True}
    with yt_dlp.YoutubeDL(opsi) as ydl:
        ydl.download([url_youtube])
    return nama_file

def potong_dinamis(file_masukan, file_keluaran, waktu_mulai, waktu_selesai):
    mp_deteksi_wajah = mp.solutions.face_detection
    pendeteksi_wajah = mp_deteksi_wajah.FaceDetection(model_selection=0, min_detection_confidence=0.5)
    
    def cari_tengah_wajah(frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hasil = pendeteksi_wajah.process(frame_rgb)
        if hasil.detections:
            kotak = hasil.detections[0].location_data.relative_bounding_box
            tinggi, lebar, _ = frame.shape
            return int((kotak.xmin + kotak.width / 2) * lebar)
        return None

    video = VideoFileClip(file_masukan).subclip(waktu_mulai, waktu_selesai)
    lebar_asli, tinggi_asli = video.w, video.h
    lebar_baru = int(tinggi_asli * 9 / 16)
    
    posisi_kamera = {"tengah": lebar_asli // 2, "target_stabil": lebar_asli // 2}
    
    def proses_frame(get_frame, t):
        frame = get_frame(t)
        deteksi_tengah = cari_tengah_wajah(frame)
        if deteksi_tengah is not None:
            if abs(deteksi_tengah - posisi_kamera["target_stabil"]) > 30:
                posisi_kamera["target_stabil"] = deteksi_tengah
        posisi_kamera["tengah"] = int((posisi_kamera["tengah"] * 0.95) + (posisi_kamera["target_stabil"] * 0.05))
        
        x1 = max(0, posisi_kamera["tengah"] - (lebar_baru // 2))
        x2 = min(lebar_asli, x1 + lebar_baru)
        if x2 > lebar_asli: x2, x1 = lebar_asli, lebar_asli - lebar_baru
        if x1 < 0: x1, x2 = 0, lebar_baru
        return frame[:, int(x1):int(x2)]

    video_dinamis = video.fl(proses_frame)
    video_dinamis.write_videofile(file_keluaran, codec="libx264", audio_codec="aac", bitrate="8000k", preset="ultrafast", threads=4, logger=None)

def buat_subtitle(file_video, file_srt):
    model = whisper.load_model("base")
    hasil = model.transcribe(file_video, word_timestamps=True)
    with open(file_srt, "w", encoding="utf-8") as f:
        urutan = 1
        for segmen in hasil["segments"]:
            if "words" in segmen:
                for kata_info in segmen["words"]:
                    jam, menit, detik_sisa = int(kata_info["start"] // 3600), int((kata_info["start"] % 3600) // 60), int(kata_info["start"] % 60)
                    mili = int((kata_info["start"] - int(kata_info["start"])) * 1000)
                    mulai_srt = f"{jam:02}:{menit:02}:{detik_sisa:02},{mili:03}"
                    
                    jam2, menit2, detik_sisa2 = int(kata_info["end"] // 3600), int((kata_info["end"] % 3600) // 60), int(kata_info["end"] % 60)
                    mili2 = int((kata_info["end"] - int(kata_info["end"])) * 1000)
                    selesai_srt = f"{jam2:02}:{menit2:02}:{detik_sisa2:02},{mili2:03}"
                    
                    f.write(f"{urutan}\n{mulai_srt} --> {selesai_srt}\n{kata_info['word'].strip()}\n\n")
                    urutan += 1

def render_final(file_masukan, file_srt, file_keluaran):
    gaya_aktif = "FontName=Poppins,FontSize=16,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Shadow=0,Alignment=2,MarginV=80,Bold=1"
    filter_video = f"subtitles={file_srt}:force_style='{gaya_aktif}'"
    perintah = ['ffmpeg', '-i', file_masukan, '-vf', filter_video, '-c:a', 'copy', '-y', file_keluaran]
    subprocess.run(perintah, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==========================================
# ANTARMUKA PENGGUNA (INPUT WEB)
# ==========================================
link_input = st.text_input("🔗 Link YouTube Video", placeholder="https://www.youtube.com/watch?v=...")
timestamp_input = st.text_input("⏱️ Masukkan Timestamp (Format: Mulai,Selesai | Mulai,Selesai)", placeholder="Contoh: 255,293 | 1126,1161 | 185,217")
nama_proyek = st.text_input("📁 Nama Proyek", value="Klip_Viral")

if st.button("🚀 PRODUKSI KLIP SEKARANG", use_container_width=True):
    if not link_input or not timestamp_input:
        st.error("⚠️ Link YouTube dan Timestamp wajib diisi!")
    else:
        try:
            # Mengolah input teks menjadi list angka
            waktu_list = timestamp_input.strip().split('|')
            daftar_momen = []
            for w in waktu_list:
                mulai, selesai = w.split(',')
                daftar_momen.append((int(mulai.strip()), int(selesai.strip())))
                
            st.success(f"Ditemukan {len(daftar_momen)} klip untuk diproses!")
            file_unduhan = "youtube_mentah.mp4"
            
            with st.status("Mengunduh Video Induk...", expanded=True) as status:
                if not os.path.exists(file_unduhan):
                    unduh_youtube(link_input, file_unduhan)
                st.write("✔️ Video berhasil disiapkan.")
                
                # Looping produksi massal
                for index, (detik_mulai, detik_selesai) in enumerate(daftar_momen, start=1):
                    nama_output = f"{nama_proyek}_PART_{index}.mp4"
                    file_sementara_video = f"temp_crop_{index}.mp4"
                    file_sementara_srt = f"temp_sub_{index}.srt"
                    
                    st.write(f"⚙️ Memproses Klip {index}/{len(daftar_momen)} (Detik {detik_mulai}-{detik_selesai})...")
                    potong_dinamis(file_unduhan, file_sementara_video, detik_mulai, detik_selesai)
                    buat_subtitle(file_sementara_video, file_sementara_srt)
                    render_final(file_sementara_video, file_sementara_srt, nama_output)
                    
                    if os.path.exists(file_sementara_video): os.remove(file_sementara_video)
                    if os.path.exists(file_sementara_srt): os.remove(file_sementara_srt)
                    
                    # Tampilkan video yang sudah jadi di Web
                    st.video(nama_output)
                    
                status.update(label="Produksi Selesai!", state="complete", expanded=False)
                st.balloons()
                
        except Exception as e:
            st.error(f"Terjadi kesalahan format atau sistem: {e}")