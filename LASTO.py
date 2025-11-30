import streamlit as st
import html
st.set_page_config(
    page_title="AI Wellness Guardian",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)
import pandas as pd
import numpy as np
import time 
import requests
import joblib
import os
import re
import tempfile
import warnings
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
import mysql.connector
from mysql.connector import Error
import hashlib

# Transformers imports - optional for mood detection
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    TRANSFORMERS_AVAILABLE = False
    pipeline = None
    print(f"⚠️ Transformers library not available: {e}")
    print("⚠️ Mood detection features will be limited. Install with: pip install transformers torch")
except Exception as e:
    TRANSFORMERS_AVAILABLE = False
    pipeline = None
    print(f"⚠️ Error loading transformers: {e}")

# NLTK imports removed - not used in the codebase

# TextBlob import with error handling
try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

warnings.filterwarnings('ignore')

# YOLO v11 Fitness Model imports
try:
    import cv2
    from yolo_fitness_model import YOLOFitnessTrainer
    YOLO_AVAILABLE = True
except ImportError as e:
    YOLO_AVAILABLE = False
    cv2 = None
    YOLOFitnessTrainer = None
    print(f"⚠️ YOLO Fitness Model not available: {e}")
except Exception as e:
    YOLO_AVAILABLE = False
    cv2 = None
    YOLOFitnessTrainer = None
    print(f"⚠️ Error loading YOLO Fitness Model: {e}")

# Directory for local exercise demo videos (user can drop .mp4 files here)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXERCISE_VIDEO_DIR = os.path.join(BASE_DIR, "exercise_videos")
os.makedirs(EXERCISE_VIDEO_DIR, exist_ok=True)


# --- Database (MySQL) connection and initialization ---
def get_database_connection():
    """Get a fresh database connection with timeout"""
    try:
        # Use shorter timeout to prevent blocking
        conn = mysql.connector.connect(
            host="mysql-1eae3245-alymohamedahmed1234-dc68.g.aivencloud.com",
            user="avnadmin",
            password="AVNS_4kyAq-NIrwVT_AMv3H5",
            autocommit=True,
            port = 19956,
            ssl_ca = "ca.pem",
            connect_timeout=2,  # Reduced from 5 to 2 seconds
            raise_on_warnings=False
        )
        return conn
    except Error as e:
        # Silent fail - don't print errors that might spam the console
        return None
    except Exception as e:
        # Silent fail
        return None

def initialize_database():
    """Initialize database and tables"""
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS wellness_db")
        cursor.execute("USE wellness_db")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255),
                password_hash VARCHAR(255),
                age INT,
                height DECIMAL(5,2),
                weight DECIMAL(5,2),
                gender VARCHAR(10),
                mode VARCHAR(100),
                physical_activity_level VARCHAR(50),
                stress_level VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("DESCRIBE users")
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        missing_columns = {
            'physical_activity_level': 'VARCHAR(50)',
            'stress_level': 'VARCHAR(50)',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'
        }
        
        for col_name, col_type in missing_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except Error:
                    pass
        
        try:
            cursor.execute("SHOW COLUMNS FROM users WHERE Field = 'mode'")
            mode_col = cursor.fetchone()
            if mode_col and 'varchar(20)' in mode_col[1].lower():
                cursor.execute("ALTER TABLE users MODIFY COLUMN mode VARCHAR(100)")
        except Error:
            pass
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Error:
        try:
            conn.close()
        except:
            pass
        return False

# Database initialization flag - will be initialized lazily when needed
_db_initialized = False

def ensure_database_initialized():
    """Lazy database initialization - only runs when needed"""
    global _db_initialized
    if _db_initialized:
        return True
    
    try:
        # Use a very short timeout to avoid blocking
        result = initialize_database()
        _db_initialized = True
        return result
    except Exception as e:
        # Don't print errors at startup - just mark as not initialized
        _db_initialized = False
        return False

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def safe_convert_db_value(value, target_type):
    """Safely convert database values to target type"""
    if value is None:
        return None
    try:
        if target_type == float:
            return float(value)
        elif target_type == int:
            return int(value)
        else:
            return value
    except (ValueError, TypeError):
        return None

def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

try:
    from streamlit_lottie import st_lottie
except Exception:
    st_lottie = None

# Define color palette - Professional & Eye-Comfortable
PRIMARY = "#5B8DEF"  # Soft professional blue
PRIMARY_DARK = "#3A6BC7"  # Deeper blue for gradients
ACCENT = "#4ECDC4"  # Soft teal/cyan
ACCENT_DARK = "#3BA89F"  # Darker accent
BG = "#1A1F2E"  # Warmer, softer dark background
BG_SECONDARY = "#1E2332"  # Secondary background
CARD_BG = "#252B3D"  # Softer card background with better contrast
CARD_BG_HOVER = "#2A3145"  # Hover state
TEXT = "#F5F7FA"  # Softer white for better readability
TEXT_SECONDARY = "#E8EBF0"  # Secondary text
MUTED = "#9CA5B8"  # Better muted color
SUCCESS = "#52C9A2"  # Success green
WARNING = "#F5A623"  # Warning amber
ERROR = "#E85D75"  # Error red

st.markdown(f"""
    <style>
    /* Main App Background - Animated Gradient */
    .stApp {{
        background: linear-gradient(-45deg, 
            {BG_SECONDARY} 0%, 
            {BG} 25%, 
            #151920 50%, 
            {BG} 75%, 
            {BG_SECONDARY} 100%);
        background-size: 400% 400%;
        animation: gradient-flow 15s ease infinite;
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, Roboto, Arial, sans-serif;
        min-height: 100vh;
        position: relative;
    }}
    
    .stApp::before {{
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: 
            radial-gradient(circle at 20% 50%, rgba(91,141,239,0.1) 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, rgba(78,205,196,0.1) 0%, transparent 50%);
        pointer-events: none;
        animation: pulse-glow 8s ease-in-out infinite;
    }}
    
    @keyframes gradient-flow {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    
    @keyframes pulse-glow {{
        0%, 100% {{ opacity: 0.5; }}
        50% {{ opacity: 0.8; }}
    }}
    
    /* Global Text Color */
    html, body, [class*="css"] {{
        color: {TEXT};
    }}

    /* Sidebar - Modern Glassmorphism Design */
    section[data-testid="stSidebar"] > div {{
        background: linear-gradient(180deg, 
            rgba(30, 35, 50, 0.95) 0%, 
            rgba(26, 31, 46, 0.98) 100%) !important;
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border-right: 1px solid rgba(255,255,255,0.1);
        box-shadow: 4px 0 40px rgba(0,0,0,0.4), 
                    inset -1px 0 0 rgba(255,255,255,0.05);
    }}
    
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        color: {TEXT};
    }}
    
    /* Sidebar Title - Animated */
    section[data-testid="stSidebar"] h1 {{
        background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradient-shift 3s ease infinite;
        background-size: 200% 200%;
    }}
    
    @keyframes gradient-shift {{
        0%, 100% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
    }}
    
    /* Modern Navigation Selectbox */
    .stSelectbox > div > div {{
        background: {CARD_BG} !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
    }}
    
    .stSelectbox > div > div:hover {{
        border-color: {PRIMARY} !important;
        box-shadow: 0 6px 20px rgba(91,141,239,0.3) !important;
        transform: translateY(-1px);
    }}
    
    .stSelectbox > div > div > select {{
        background: transparent !important;
        color: {TEXT} !important;
        font-weight: 600 !important;
        padding: 0.75rem 1rem !important;
    }}
    
    /* Sidebar Button Enhancements */
    section[data-testid="stSidebar"] .stButton > button {{
        background: linear-gradient(135deg, {CARD_BG} 0%, {CARD_BG_HOVER} 100%);
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        border-color: {PRIMARY};
        transform: translateX(4px);
        box-shadow: 0 6px 20px rgba(91,141,239,0.4);
    }}

    /* Buttons - Ultra Modern with Animations */
    .stButton > button {{
        background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        color: #ffffff;
        border: 0;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        border-radius: 14px;
        box-shadow: 0 4px 20px rgba(91,141,239,0.35),
                    inset 0 1px 0 rgba(255,255,255,0.2);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        letter-spacing: 0.3px;
        position: relative;
        overflow: hidden;
        transform: perspective(1000px) translateZ(0);
    }}
    
    .stButton > button::before {{
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }}
    
    .stButton > button:hover::before {{
        width: 300px;
        height: 300px;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-3px) scale(1.02) perspective(1000px) translateZ(10px);
        filter: brightness(1.15);
        box-shadow: 0 12px 35px rgba(91,141,239,0.5),
                    inset 0 1px 0 rgba(255,255,255,0.3),
                    0 0 30px rgba(91,141,239,0.3);
        background: linear-gradient(135deg, #6B9DFF 0%, #4A7BD7 100%);
    }}
    
    .stButton > button:active {{
        transform: translateY(-1px) scale(0.98);
        box-shadow: 0 4px 15px rgba(91,141,239,0.4);
        transition: all 0.1s ease;
    }}
    
    /* Secondary Button Styling */
    .stButton > button[kind="secondary"] {{
        background: linear-gradient(135deg, {CARD_BG} 0%, {CARD_BG_HOVER} 100%);
        color: {TEXT};
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}
    .stButton > button[kind="secondary"]:hover {{
        background: linear-gradient(135deg, {CARD_BG_HOVER} 0%, #2F3649 100%);
        border-color: rgba(255,255,255,0.15);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }}

    /* Typography - Enhanced with Animations */
    h1, h2, h3, h4, h5, h6 {{
        color: {TEXT};
        letter-spacing: 0.3px;
        font-weight: 700;
        animation: fadeInUp 0.6s ease-out;
    }}
    h1 {{
        font-weight: 800;
        font-size: 2.5rem;
        background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 50%, {PRIMARY} 100%);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradient-shift 3s ease infinite, fadeInUp 0.6s ease-out;
        position: relative;
    }}
    
    h1::after {{
        content: '';
        position: absolute;
        bottom: -5px;
        left: 0;
        width: 0;
        height: 3px;
        background: linear-gradient(90deg, {PRIMARY}, {ACCENT});
        animation: expand-width 1s ease-out 0.3s forwards;
    }}
    
    @keyframes expand-width {{
        to {{ width: 100%; }}
    }}
    
    h2 {{
        font-weight: 700;
        color: {TEXT_SECONDARY};
        position: relative;
        padding-left: 1rem;
    }}
    
    h2::before {{
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 4px;
        height: 60%;
        background: linear-gradient(180deg, {PRIMARY}, {ACCENT});
        border-radius: 2px;
        animation: expand-height 0.6s ease-out;
    }}
    
    @keyframes expand-height {{
        from {{ height: 0; }}
        to {{ height: 60%; }}
    }}

    /* Expanders - Modern Card Design */
    .streamlit-expanderHeader {{
        background: {CARD_BG};
        color: {TEXT};
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        transition: all 0.3s ease;
    }}
    .streamlit-expanderHeader:hover {{
        background: {CARD_BG_HOVER};
        border-color: rgba(91,141,239,0.3);
    }}
    .streamlit-expanderContent {{
        background: {BG};
        border-radius: 0 0 12px 12px;
        border: 1px solid rgba(255,255,255,0.05);
        border-top: none;
    }}

    /* Progress Bars - Animated Gradient */
    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, 
            {PRIMARY} 0%, 
            {ACCENT} 50%, 
            {PRIMARY} 100%);
        background-size: 200% 100%;
        animation: progress-shine 2s linear infinite;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(91,141,239,0.4),
                    inset 0 1px 0 rgba(255,255,255,0.2);
        position: relative;
        overflow: hidden;
    }}
    
    .stProgress > div > div > div > div::after {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, 
            transparent, 
            rgba(255,255,255,0.3), 
            transparent);
        animation: progress-sweep 2s infinite;
    }}
    
    @keyframes progress-shine {{
        0% {{ background-position: 0% 50%; }}
        100% {{ background-position: 200% 50%; }}
    }}
    
    @keyframes progress-sweep {{
        0% {{ left: -100%; }}
        100% {{ left: 100%; }}
    }}

    /* Alerts - Professional Styling */
    .stAlert {{
        background: rgba(91,141,239,0.1);
        border-left: 4px solid {PRIMARY};
        color: {TEXT};
        border-radius: 8px;
        padding: 1rem;
        backdrop-filter: blur(10px);
    }}
    div[data-baseweb="notification"] {{
        background: {CARD_BG} !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
    }}

    /* Cards - Modern Glassmorphism with Animations */
    .card {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%);
        padding: 28px;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4),
                    0 0 0 1px rgba(255,255,255,0.05),
                    inset 0 1px 0 rgba(255,255,255,0.1);
        margin-bottom: 24px;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        position: relative;
        overflow: hidden;
    }}
    
    .card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, 
            transparent, 
            rgba(91,141,239,0.1), 
            transparent);
        transition: left 0.5s ease;
    }}
    
    .card:hover::before {{
        left: 100%;
    }}
    
    .card:hover {{
        transform: translateY(-4px) scale(1.01);
        box-shadow: 0 16px 48px rgba(0,0,0,0.5),
                    0 0 0 1px rgba(91,141,239,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.15);
        border-color: rgba(91,141,239,0.3);
    }}
    
    /* Muted Text */
    .muted {{ 
        color: {MUTED}; 
        font-weight: 400;
    }}
    
    /* Badges - Modern Design */
    .badge {{
        display: inline-block;
        padding: 5px 12px;
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(78,205,196,0.2) 0%, rgba(78,205,196,0.15) 100%);
        color: {ACCENT};
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
        border: 1px solid rgba(78,205,196,0.3);
        box-shadow: 0 2px 8px rgba(78,205,196,0.2);
    }}
    
    /* Hero Section - Animated Glassmorphism */
    .hero {{
        position: relative;
        overflow: hidden;
        background: linear-gradient(135deg, 
            rgba(91,141,239,0.15) 0%, 
            rgba(78,205,196,0.12) 50%, 
            rgba(91,141,239,0.1) 100%);
        border-radius: 24px;
        padding: 32px 36px;
        border: 1px solid rgba(255,255,255,0.15);
        box-shadow: 0 12px 40px rgba(0,0,0,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.1),
                    0 0 60px rgba(91,141,239,0.1);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        animation: hero-float 6s ease-in-out infinite;
    }}
    
    .hero::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(91,141,239,0.1) 0%, transparent 70%);
        animation: rotate-glow 20s linear infinite;
        pointer-events: none;
    }}
    
    @keyframes hero-float {{
        0%, 100% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-8px); }}
    }}
    
    @keyframes rotate-glow {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    
    /* Glow Effect - Animated */
    .glow {{ 
        filter: drop-shadow(0 0 20px rgba(91,141,239,0.4)); 
        animation: glow-pulse 2s ease-in-out infinite;
    }}
    
    @keyframes glow-pulse {{
        0%, 100% {{
            filter: drop-shadow(0 0 20px rgba(91,141,239,0.4));
        }}
        50% {{
            filter: drop-shadow(0 0 30px rgba(91,141,239,0.6));
        }}
    }}
    
    /* Metrics - Animated Glass Cards */
    .metric {{
        background: linear-gradient(135deg, 
            rgba(255,255,255,0.1) 0%, 
            rgba(255,255,255,0.05) 100%);
        border: 1px solid rgba(255,255,255,0.15);
        padding: 24px;
        border-radius: 18px;
        text-align: center;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        backdrop-filter: blur(15px) saturate(180%);
        -webkit-backdrop-filter: blur(15px) saturate(180%);
        box-shadow: 0 8px 24px rgba(0,0,0,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
    }}
    
    .metric::after {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, 
            transparent, 
            rgba(91,141,239,0.2), 
            transparent);
        transition: left 0.6s ease;
    }}
    
    .metric:hover::after {{
        left: 100%;
    }}
    
    .metric:hover {{
        background: linear-gradient(135deg, 
            rgba(91,141,239,0.15) 0%, 
            rgba(78,205,196,0.12) 100%);
        border-color: rgba(91,141,239,0.4);
        transform: translateY(-4px) scale(1.03);
        box-shadow: 0 12px 32px rgba(91,141,239,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.2),
                    0 0 40px rgba(91,141,239,0.2);
    }}
    .metric .label {{ 
        color: {MUTED}; 
        font-size: 13px; 
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }}
    .metric .value {{ 
        color: {TEXT}; 
        font-weight: 800; 
        font-size: 28px;
        margin-top: 8px;
    }}
    
    /* Input Fields - Animated Modern Design */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%) !important;
        backdrop-filter: blur(10px) saturate(180%) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 12px !important;
        color: {TEXT} !important;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.05) !important;
        padding: 0.75rem 1rem !important;
    }}
    
    .stTextInput > div > div > input:hover,
    .stNumberInput > div > div > input:hover {{
        border-color: rgba(91,141,239,0.4) !important;
        box-shadow: 0 6px 20px rgba(91,141,239,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.1) !important;
        transform: translateY(-1px);
    }}
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {{
        border-color: {PRIMARY} !important;
        box-shadow: 0 0 0 4px rgba(91,141,239,0.25),
                    0 8px 25px rgba(91,141,239,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.15) !important;
        background: linear-gradient(135deg, 
            rgba(42, 49, 69, 0.9) 0%, 
            rgba(37, 43, 61, 0.7) 100%) !important;
        transform: translateY(-2px) scale(1.01);
        outline: none !important;
    }}
    
    /* Selectbox Styling */
    .stSelectbox > div > div {{
        background: {CARD_BG} !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
    }}
    
    /* Text Area - Enhanced */
    .stTextArea > div > div > textarea {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%) !important;
        backdrop-filter: blur(10px) saturate(180%) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 12px !important;
        color: {TEXT} !important;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.05) !important;
    }}
    
    .stTextArea > div > div > textarea:hover {{
        border-color: rgba(91,141,239,0.4) !important;
        box-shadow: 0 6px 20px rgba(91,141,239,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.1) !important;
    }}
    
    .stTextArea > div > div > textarea:focus {{
        border-color: {PRIMARY} !important;
        box-shadow: 0 0 0 4px rgba(91,141,239,0.25),
                    0 8px 25px rgba(91,141,239,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.15) !important;
        background: linear-gradient(135deg, 
            rgba(42, 49, 69, 0.9) 0%, 
            rgba(37, 43, 61, 0.7) 100%) !important;
        outline: none !important;
    }}
    
    /* Success, Warning, Error Messages */
    .stSuccess {{
        background: rgba(82,201,162,0.15) !important;
        border-left: 4px solid {SUCCESS} !important;
        color: {TEXT} !important;
        border-radius: 8px !important;
    }}
    .stWarning {{
        background: rgba(245,166,35,0.15) !important;
        border-left: 4px solid {WARNING} !important;
        color: {TEXT} !important;
        border-radius: 8px !important;
    }}
    .stError {{
        background: rgba(232,93,117,0.15) !important;
        border-left: 4px solid {ERROR} !important;
        color: {TEXT} !important;
        border-radius: 8px !important;
    }}
    .stInfo {{
        background: rgba(91,141,239,0.15) !important;
        border-left: 4px solid {PRIMARY} !important;
        color: {TEXT} !important;
        border-radius: 8px !important;
    }}
    
    /* Tabs - Ultra Modern with Animations */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border-radius: 14px;
        padding: 8px;
        margin-bottom: 2rem;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.1);
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        border-radius: 10px;
        padding: 0.85rem 1.6rem;
        font-weight: 600;
        color: {MUTED};
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        font-size: 0.95rem;
        position: relative;
        overflow: hidden;
    }}
    
    .stTabs [data-baseweb="tab"]::before {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        width: 0;
        height: 2px;
        background: {PRIMARY};
        transform: translateX(-50%);
        transition: width 0.3s ease;
    }}
    
    .stTabs [data-baseweb="tab"]:hover::before {{
        width: 60%;
    }}
    
    .stTabs [data-baseweb="tab"]:hover {{
        color: {TEXT};
        background: rgba(91,141,239,0.1);
    }}
    
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        color: white;
        box-shadow: 0 6px 20px rgba(91,141,239,0.4),
                    inset 0 1px 0 rgba(255,255,255,0.2);
        transform: scale(1.02);
    }}
    
    .stTabs [aria-selected="true"]::before {{
        width: 80%;
    }}
    
    /* Slider Styling */
    .stSlider {{
        color: {PRIMARY} !important;
    }}
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {{
        color: {TEXT} !important;
        font-weight: 700 !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: {MUTED} !important;
    }}
    
    /* Scrollbar - Modern Styling */
    ::-webkit-scrollbar {{
        width: 12px;
        height: 12px;
    }}
    ::-webkit-scrollbar-track {{
        background: {BG};
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%);
        border-radius: 10px;
        border: 2px solid {BG};
        box-shadow: inset 0 0 6px rgba(0,0,0,0.3);
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: linear-gradient(135deg, #6B9DFF 0%, #5ED4CC 100%);
        box-shadow: 0 0 10px rgba(91,141,239,0.5);
    }}
    
    /* Page Transition Animations */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(20px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    
    .main .block-container {{
        animation: fadeInUp 0.6s ease-out;
    }}
    
    /* Floating Animation for Icons */
    @keyframes float {{
        0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
        33% {{ transform: translateY(-10px) rotate(2deg); }}
        66% {{ transform: translateY(5px) rotate(-2deg); }}
    }}
    
    /* Pulse Animation */
    @keyframes pulse {{
        0%, 100% {{ transform: scale(1); opacity: 1; }}
        50% {{ transform: scale(1.05); opacity: 0.8; }}
    }}
    
    /* Shimmer Effect */
    @keyframes shimmer {{
        0% {{ background-position: -1000px 0; }}
        100% {{ background-position: 1000px 0; }}
    }}
    
    /* Badge Glow Animation */
    .badge.glow {{
        animation: pulse-glow 2s ease-in-out infinite;
        box-shadow: 0 0 20px rgba(78,205,196,0.5),
                    0 0 40px rgba(78,205,196,0.3);
    }}
    
    /* Enhanced Expander Animations */
    .streamlit-expanderHeader {{
        position: relative;
    }}
    
    .streamlit-expanderHeader::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 0;
        height: 2px;
        background: linear-gradient(90deg, {PRIMARY}, {ACCENT});
        transition: width 0.3s ease;
    }}
    
    .streamlit-expanderHeader:hover::after {{
        width: 100%;
    }}
    
    /* Metric Value Animation */
    .metric .value {{
        animation: count-up 1s ease-out;
    }}
    
    @keyframes count-up {{
        from {{
            opacity: 0;
            transform: scale(0.8);
        }}
        to {{
            opacity: 1;
            transform: scale(1);
        }}
    }}
    
    /* Success/Warning/Error Enhanced */
    .stSuccess, .stWarning, .stError, .stInfo {{
        animation: slideInRight 0.5s ease-out;
        position: relative;
        overflow: hidden;
    }}
    
    .stSuccess::before, .stWarning::before, 
    .stError::before, .stInfo::before {{
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
        background: currentColor;
        animation: expand-left 0.5s ease-out;
    }}
    
    @keyframes slideInRight {{
        from {{
            opacity: 0;
            transform: translateX(20px);
        }}
        to {{
            opacity: 1;
            transform: translateX(0);
        }}
    }}
    
    @keyframes expand-left {{
        from {{ width: 0; }}
        to {{ width: 4px; }}
    }}
    
    /* Enhanced Page Layouts */
    .page-container {{
        animation: fadeInUp 0.6s ease-out;
        padding: 1rem 0;
    }}
    
    /* Interactive Card Hover Effects */
    .interactive-card {{
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
    }}
    
    .interactive-card:hover {{
        transform: translateY(-6px) scale(1.02);
    }}
    
    /* Smooth Page Transitions */
    .main .block-container {{
        transition: opacity 0.3s ease, transform 0.3s ease;
    }}
    
    /* Enhanced Spacing for Better Layout */
    .stMarkdown {{
        margin-bottom: 1rem;
    }}
    
    /* Better Column Spacing */
    [data-testid="column"] {{
        padding: 0.5rem;
    }}
    
    /* Improved Form Layouts */
    .stForm {{
        padding: 1.5rem;
        background: rgba(30, 35, 50, 0.3);
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.08);
    }}
    
    /* Enhanced Metric Display */
    [data-testid="stMetricContainer"] {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.6) 0%, 
            rgba(42, 49, 69, 0.4) 100%);
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.3s ease;
    }}
    
    [data-testid="stMetricContainer"]:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(91,141,239,0.2);
        border-color: rgba(91,141,239,0.3);
    }}
    
    /* Better Info/Warning/Success Layout */
    .stAlert > div {{
        padding: 1.25rem;
        border-radius: 12px;
    }}
    
    /* Enhanced Selectbox in Forms */
    .stSelectbox > div > div > select {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%) !important;
        color: {TEXT} !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 12px !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.3s ease !important;
    }}
    
    .stSelectbox > div > div > select:hover {{
        border-color: rgba(91,141,239,0.4) !important;
        box-shadow: 0 4px 15px rgba(91,141,239,0.2) !important;
    }}
    
    .stSelectbox > div > div > select:focus {{
        border-color: {PRIMARY} !important;
        box-shadow: 0 0 0 3px rgba(91,141,239,0.25) !important;
        outline: none !important;
    }}
    
    /* Enhanced Number Input */
    .stNumberInput > div > div > input {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 12px !important;
        color: {TEXT} !important;
        transition: all 0.3s ease !important;
    }}
    
    /* Better Radio Button Styling */
    .stRadio > div {{
        background: rgba(30, 35, 50, 0.4);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.08);
    }}
    
    /* Enhanced Slider */
    .stSlider > div > div {{
        background: rgba(37, 43, 61, 0.6);
        border-radius: 12px;
        padding: 1rem;
    }}
    
    /* Better Time Input */
    .stTimeInput > div > div > input {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 12px !important;
        color: {TEXT} !important;
    }}
    
    /* Improved Spinner */
    .stSpinner > div {{
        border-top-color: {PRIMARY} !important;
        border-right-color: {ACCENT} !important;
    }}
    
    /* Enhanced Chat Messages */
    .stChatMessage {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.6) 0%, 
            rgba(42, 49, 69, 0.4) 100%);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }}
    
    .stChatMessage:hover {{
        border-color: rgba(91,141,239,0.3);
        box-shadow: 0 4px 15px rgba(91,141,239,0.15);
    }}
    
    /* Better Plotly Chart Containers */
    .js-plotly-plot {{
        border-radius: 16px;
        overflow: hidden;
    }}
    
    /* Enhanced Table Styling */
    .stDataFrame {{
        border-radius: 12px;
        overflow: hidden;
    }}
    
    /* Smooth Scroll Behavior */
    html {{
        scroll-behavior: smooth;
    }}
    
    /* Loading States */
    @keyframes shimmer {{
        0% {{ background-position: -1000px 0; }}
        100% {{ background-position: 1000px 0; }}
    }}
    
    .loading-shimmer {{
        background: linear-gradient(
            90deg,
            rgba(37, 43, 61, 0.4) 0%,
            rgba(91,141,239,0.2) 50%,
            rgba(37, 43, 61, 0.4) 100%
        );
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
    }}
    </style>
""", unsafe_allow_html=True)

# Lazy load hero animation - will load when needed
hero_anim = None
def get_hero_animation():
    """Lazy load hero animation to avoid blocking startup"""
    global hero_anim
    if hero_anim is None:
        hero_anim = load_lottieurl("https://assets3.lottiefiles.com/packages/lf20_4kx2q32n.json")
    return hero_anim

# Initialize session state
if 'user_data' not in st.session_state:
    st.session_state.user_data = {
        'age': None,
        'weight': None,
        'height': None,
        'mode': None,
        'logged_in': False,
        'bmi': None,
        'target_calories': None
    }

if 'login_state' not in st.session_state:
    st.session_state.login_state = {
        'is_logged_in': False,
        'is_guest': False,
        'username': None,
        'user_type': None
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'current_user' not in st.session_state:
    st.session_state.current_user = None

if 'mood_history' not in st.session_state:
    st.session_state.mood_history = []

if 'sleep_data' not in st.session_state:
    st.session_state.sleep_data = []

if 'health_metrics' not in st.session_state:
    st.session_state.health_metrics = {
        'daily_calories': 0,
        'water_intake': 0,
        'exercise_minutes': 0,
        'sleep_hours': 0,
        'mood_score': 0
    }

if 'daily_goals' not in st.session_state:
    st.session_state.daily_goals = {
        'water_goal': 8,  # glasses
        'exercise_goal': 30,  # minutes
        'sleep_goal': 8,  # hours
        'calories_goal': 2000
    }

if 'health_journal' not in st.session_state:
    st.session_state.health_journal = []

if 'meal_log' not in st.session_state:
    st.session_state.meal_log = []

if 'weight_history' not in st.session_state:
    st.session_state.weight_history = []

if 'achievements' not in st.session_state:
    st.session_state.achievements = {
        'streak_days': 0,
        'total_workouts': 0,
        'badges': []
    }

# Additional safety checks
if 'selected_page_index' not in st.session_state:
    st.session_state.selected_page_index = 0

if 'current_page' not in st.session_state:
    st.session_state.current_page = "Home"

# Ensure chat_history is always a list
if not isinstance(st.session_state.get('chat_history', []), list):
    st.session_state.chat_history = []

# Ensure mood_history is always a list
if not isinstance(st.session_state.get('mood_history', []), list):
    st.session_state.mood_history = []

# Ensure sleep_data is always a list
if not isinstance(st.session_state.get('sleep_data', []), list):
    st.session_state.sleep_data = []

# Ensure meal_log is always a list
if not isinstance(st.session_state.get('meal_log', []), list):
    st.session_state.meal_log = []

# Ensure weight_history is always a list
if not isinstance(st.session_state.get('weight_history', []), list):
    st.session_state.weight_history = []

# Ensure health_journal is always a list
if not isinstance(st.session_state.get('health_journal', []), list):
    st.session_state.health_journal = []

# Utility functions
def calculate_bmi(weight, height):
    """Calculate BMI from weight and height"""
    try:
        weight = float(weight) if weight else 0.0
        height = float(height) if height else 0.0
        
        if weight <= 0 or height <= 0:
            return 0.0
            
        height_m = height / 100
        return weight / (height_m ** 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0

def calculate_target_calories(weight, height, age, mode, gender='male'):
    """Calculate target daily calories based on user profile"""
    try:
        weight = float(weight) if weight else 0.0
        height = float(height) if height else 0.0
        age = int(age) if age else 0
        
        if weight <= 0 or height <= 0 or age <= 0:
            return 2000
        
        bmi = calculate_bmi(weight, height)
        
        if gender and gender.lower() == 'male':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        activity_factor = 1.55
        tdee = bmr * activity_factor
        
        if mode and 'bulk' in mode.lower():
            return int(tdee + 500)
        else:
            return int(tdee - 500)
            
    except (ValueError, TypeError, ZeroDivisionError):
        return 2000

def predict_calories(food_data):
    """Predict calories using trained model"""
    serving_size = food_data.get('serving_size', 1.0)
    protein = food_data.get('protein', 0)
    carbs = food_data.get('carbs', 0)
    fat = food_data.get('fat', 0)
    
    estimated_calories = (protein * 4) + (carbs * 4) + (fat * 9) * serving_size
    return float(estimated_calories)

def load_sleep_disorder_model():
    try:
        # Try best_random_model.pkl first, then random_model.pkl as fallback
        model_path = os.path.join(BASE_DIR, "best_random_model.pkl")
        if not os.path.exists(model_path):
            model_path = os.path.join(BASE_DIR, "random_model.pkl")
        model = joblib.load(model_path)
        return model
    except Exception as e:
        st.error(f"❌ Could not load model: {e}")
        return None
    
def load_mood_model():
    """Load mood detection model from Hugging Face"""
    if not TRANSFORMERS_AVAILABLE or pipeline is None:
        print("⚠️ Transformers not available. Mood detection disabled.")
        return None
    
    try:
        print("⏳ Loading model directly from Hugging Face...")
        model = pipeline(
            "text-classification",
            model="SamLowe/roberta-base-go_emotions",
            top_k=None,
            return_all_scores=True
        )
        print("✅ Model loaded successfully.")
        return model
    except Exception as e:
        print(f"⚠️ Error loading mood model: {e}")
        return None

# Load mood model if transformers is available (lazy loading - will load when needed)
mood_model = None
EMOJI_DICT = {
    "admiration": "✨",
    "amusement": "😄",
    "anger": "😡",
    "annoyance": "😤",
    "approval": "👍",
    "caring": "🤗",
    "confusion": "🤔",
    "curiosity": "🧐",
    "desire": "🔥",
    "disappointment": "😞",
    "disapproval": "👎",
    "disgust": "🤢",
    "embarrassment": "😳",
    "excitement": "🤩",
    "fear": "😨",
    "gratitude": "🙏",
    "grief": "💔",
    "joy": "😊",
    "love": "❤️",
    "neutral": "😐",
    "nervousness": "😬",
    "optimism": "🙂",
    "pride": "🏅",
    "realization": "💡",
    "relief": "😌",
    "remorse": "😔",
    "sadness": "😢",
    "surprise": "😲"
}

def analyze_mood(text, model, threshold=0.3):
    if model is None or not text.strip():
        return "Unknown", 0.0, "❓"

    pattern = r"\b(?:but|and|although|though|however|whereas|while|yet|despite|even though|on the other hand|nevertheless)\b|[;,\-]"
    clauses = re.split(pattern, text, flags=re.IGNORECASE)

    all_emotions = {}
    print(f"\n📝 Text: {text}")

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        preds = model(clause)[0]
        top_emotions = [p for p in preds if p["score"] >= threshold]

        if top_emotions:
            print(f"  → Clause: \"{clause}\"")
            for p in top_emotions:
                print(f"     - {p['label']}: {p['score']:.2f}")
                all_emotions[p['label']] = all_emotions.get(p['label'], 0) + p['score']

    if not all_emotions:
        return "Unknown", 0.0, "❓"

    final_label = max(all_emotions, key=all_emotions.get)
    final_score = round(all_emotions[final_label] / len(clauses), 2)
    emoji = EMOJI_DICT.get(final_label.lower(), "🙂")

    print(f"\n💡 Dominant Emotion: {final_label} ({final_score}) {emoji}")
    return final_label, final_score, emoji

# Load model with caching for Fake News Detection
@st.cache_resource
def load_fake_news_model():
    """Load the zero-shot classification model once and cache it"""
    if not TRANSFORMERS_AVAILABLE or pipeline is None:
        return None
    
    try:
        # Force CPU to avoid meta tensor issues
        # device=-1 means CPU, device=0 means first GPU
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=-1)
    except Exception as e:
        st.error(f"⚠️ Error loading fake news detection model: {e}")
        return None

# Sensational and credible word lists
SENSATIONAL_WORDS = [
    'miracle', 'instant', 'overnight', 'secret', 'shocking', 'amazing',
    'breakthrough', 'revolutionary', 'guaranteed', 'never', 'always',
    'cure-all', 'magic', 'incredible', 'unbelievable', 'hidden truth'
]

CREDIBLE_WORDS = [
    'study', 'clinical', 'evidence', 'research', 'trial', 'peer-reviewed',
    'journal', 'scientist', 'doctor', 'published', 'data', 'statistics',
    'analysis', 'findings', 'results'
]

TRUSTED_SOURCES = [
    'WHO', 'World Health Organization', 'CDC', 'Centers for Disease Control',
    'FDA', 'Food and Drug Administration', 'NIH', 'National Institutes of Health',
    'university', 'hospital', 'medical school', 'Mayo Clinic', 'Johns Hopkins',
    'peer-reviewed', 'journal', 'Lancet', 'NEJM', 'BMJ'
]

def analyze_language(text):
    """Detect sensational and credible language"""
    text_lower = text.lower()
    
    sensational_found = [word for word in SENSATIONAL_WORDS if word in text_lower]
    credible_found = [word for word in CREDIBLE_WORDS if word in text_lower]
    
    return {
        'sensational_words': sensational_found,
        'sensational_count': len(sensational_found),
        'credible_words': credible_found,
        'credible_count': len(credible_found)
    }

def check_sources(text):
    """Check for trusted source mentions"""
    sources_found = [source for source in TRUSTED_SOURCES if source.lower() in text.lower()]
    return {
        'sources_found': sources_found,
        'has_trusted_sources': len(sources_found) > 0
    }

def get_final_assessment(ai_result, language_analysis, source_check):
    """
    Combine all analyses to give final assessment - AI result is primary driver
    
    CONFIDENCE SCORE EXPLANATION:
    The confidence score (0-100) represents CREDIBILITY:
    - 80-100: Highly credible (likely true)
    - 50-79:  Moderately credible (possibly true/misleading)
    - 20-49:  Low credibility (possibly false/misleading)
    - 0-19:   Very low credibility (likely false)
    
    Calculation:
    1. AI Analysis (80% weight): 
       - "true health information" → high credibility (AI confidence * 80-100)
       - "misleading" → medium credibility (50 ± adjustments)
       - "false health information" → low credibility (AI confidence * 0-20)
    
    2. Language Analysis (10% weight):
       - Credible words found → +1 to +8 points
       - Sensational words found → -1 to -8 points
    
    3. Source Check (10% weight):
       - Trusted sources found → +1 to +8 points
    """
    # Get AI prediction (this is the PRIMARY factor)
    top_label = ai_result['labels'][0]
    ai_confidence = ai_result['scores'][0]  # AI's confidence in its prediction (0-1)
    
    # Calculate base credibility score based on AI prediction
    # This represents how credible the information is (not how confident AI is in being wrong)
    if top_label == "true health information":
        # AI says it's TRUE → High credibility
        # If AI is 80% confident it's true, credibility = 80-100 range
        base_credibility = 60 + (ai_confidence * 40)  # Range: 60-100
    
    elif top_label == "misleading":
        # AI says it's MISLEADING → Medium credibility
        # Base around 50, adjusted by AI confidence
        base_credibility = 40 + (ai_confidence * 20)  # Range: 40-60
    
    else:  # false health information
        # AI says it's FALSE → Low credibility
        # If AI is 80% confident it's false, credibility should be LOW (20 or less)
        base_credibility = (1 - ai_confidence) * 30  # Range: 0-30 (inverted: high AI confidence in false = low credibility)
    
    # Language analysis adjustments (max ±8 points)
    language_adjustment = 0
    if language_analysis['credible_count'] > 0:
        # Positive boost for credible language (words like "study", "research", "evidence")
        language_adjustment += min(language_analysis['credible_count'] * 1.5, 8)
    if language_analysis['sensational_count'] > 0:
        # Negative for sensational language (words like "miracle", "secret", "guaranteed")
        language_adjustment -= min(language_analysis['sensational_count'] * 1.5, 8)
    
    # Source check adjustments (max +8 points)
    source_adjustment = 0
    if source_check['has_trusted_sources']:
        # Positive boost for trusted sources (WHO, CDC, FDA, etc.)
        source_adjustment += min(len(source_check['sources_found']) * 2, 8)
    
    # Calculate final credibility score
    # Formula: Base (from AI) + Language adjustments + Source adjustments
    final_credibility_score = base_credibility + language_adjustment + source_adjustment
    
    # Normalize to 0-100 range
    final_credibility_score = max(0, min(100, final_credibility_score))
    
    # Determine assessment message - directly based on AI prediction
    if top_label == "true health information":
        if ai_confidence >= 0.7:  # High AI confidence
            assessment_msg = f"✅ Likely Credible - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "success"
        elif ai_confidence >= 0.5:  # Medium AI confidence
            assessment_msg = f"⚠️ Possibly Credible - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "warning"
        else:  # Low AI confidence
            assessment_msg = f"⚠️ Uncertain - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "warning"
    
    elif top_label == "misleading":
        if ai_confidence >= 0.7:  # High AI confidence
            assessment_msg = f"⚠️ Likely Misleading - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "warning"
        elif ai_confidence >= 0.5:  # Medium AI confidence
            assessment_msg = f"⚠️ Possibly Misleading - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "warning"
        else:  # Low AI confidence
            assessment_msg = f"⚠️ Uncertain - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "warning"
    
    else:  # false health information
        if ai_confidence >= 0.7:  # High AI confidence it's false
            assessment_msg = f"❌ Likely False - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "error"
        elif ai_confidence >= 0.5:  # Medium AI confidence
            assessment_msg = f"❌ Possibly False - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "error"
        else:  # Low AI confidence
            assessment_msg = f"⚠️ Uncertain - AI Analysis: {top_label} ({ai_confidence*100:.1f}% confidence)"
            assessment_type = "warning"
    
    return assessment_msg, final_credibility_score, assessment_type

def generate_fake_news_report(text, ai_result, language_analysis, source_check, final_assessment, confidence_score):
    """Generate a downloadable text report"""
    # Safely get AI predictions with error handling
    top_label = ai_result['labels'][0] if ai_result and 'labels' in ai_result and len(ai_result['labels']) > 0 else "Unknown"
    top_score = ai_result['scores'][0]*100 if ai_result and 'scores' in ai_result and len(ai_result['scores']) > 0 else 0.0
    
    alt_predictions = ""
    if ai_result and 'labels' in ai_result and len(ai_result['labels']) > 1:
        for i in range(1, min(len(ai_result['labels']), 3)):
            if i < len(ai_result['scores']):
                alt_predictions += f"     - {ai_result['labels'][i]}: {ai_result['scores'][i]*100:.1f}%\n"
    if not alt_predictions:
        alt_predictions = "     - None available"
    
    report = f"""
═══════════════════════════════════════════════════════════
    HEALTH NEWS CREDIBILITY ANALYSIS REPORT
═══════════════════════════════════════════════════════════

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

ANALYZED TEXT:
{text[:500]}{"..." if len(text) > 500 else ""}

═══════════════════════════════════════════════════════════
FINAL ASSESSMENT: {final_assessment}
Confidence Score: {confidence_score:.1f}/100
═══════════════════════════════════════════════════════════

DETAILED ANALYSIS:

1. AI CLASSIFICATION:
   • Top Prediction: {top_label}
   • Confidence: {top_score:.1f}%
   • Alternative Predictions:
{alt_predictions}

2. LANGUAGE ANALYSIS:
   • Sensational Words Found ({language_analysis['sensational_count']}):
     {', '.join(language_analysis['sensational_words']) if language_analysis['sensational_words'] else 'None'}
   
   • Credible Words Found ({language_analysis['credible_count']}):
     {', '.join(language_analysis['credible_words']) if language_analysis['credible_words'] else 'None'}

3. SOURCE CHECK:
   • Trusted Sources Mentioned ({len(source_check['sources_found'])}):
     {', '.join(source_check['sources_found']) if source_check['sources_found'] else 'None'}

═══════════════════════════════════════════════════════════
DISCLAIMER:
This tool assists with analysis and is not a substitute for 
expert medical verification. Always consult healthcare 
professionals for medical advice.
═══════════════════════════════════════════════════════════
"""
    return report


def generate_chatbot_response(user_input, user_data):
    """
    Generate an empathetic, health-focused response using free Gemini models.
    Tries multiple free models in order: 2.5-flash, 2.5-flash-lite, 2.0-flash, 1.5-flash, 1.5-pro
    Falls back to the next model if one fails.
    """

    # --- API Key Configuration ---
    api_key = os.getenv("GEMINI_API_KEY") or "AIzaSyC98pj9w2ioi0PgTG5LvlnXho78t_oE6Zc"
    genai.configure(api_key=api_key)

    # --- Build Profile Summary ---
    age = user_data.get('age')
    gender = user_data.get('gender')
    bmi_val = user_data.get('bmi')
    height = user_data.get('height')
    weight = user_data.get('weight')
    goal = user_data.get('mode')
    activity = user_data.get('physical_activity_level')
    stress = user_data.get('stress_level')

    bmi_str = "{:.1f}".format(bmi_val) if isinstance(bmi_val, (int, float)) else "N/A"
    profile_info = (
        "Age: " + str(age if age is not None else 'N/A') + ", " +
        "Gender: " + str(gender if gender else 'N/A') + ", " +
        "BMI: " + str(bmi_str) + ", " +
        "Goal: " + str(goal if goal else 'N/A') + ", " +
        "Height: " + str(height if height is not None else 'N/A') + ", " +
        "Weight: " + str(weight if weight is not None else 'N/A') + ", " +
        "Activity Level: " + str(activity if activity else 'N/A') + ", " +
        "Stress Level: " + str(stress if stress else 'N/A') + "."
    )

    # --- Tone Control ---
    tone = st.session_state.get('chatbot_tone', 'Supportive')
    tone_instructions = {
        'Supportive': "Use warm, empathetic language. Keep answers short and friendly.",
        'Motivational': "Be upbeat and encouraging, with clear, action-oriented tips.",
        'Scientific': "Be concise and evidence-based, avoiding jargon and citing principles when useful."
    }.get(tone, 'Use warm, empathetic language. Keep answers short and friendly.')

    safety_clause = (
        "You are not a medical professional. Do not diagnose or prescribe. "
        "For any medical concerns, advise consulting a qualified healthcare provider."
    )

    system_prompt = (
    "You are **AURA**, an advanced, deeply empathetic AI Wellness Guardian designed to support "
    "users across physical, mental, and emotional dimensions of well-being. Your communication "
    "should feel human, warm, validating, and supportive while remaining grounded in safe, "
    "evidence-based lifestyle guidance.\n\n"

    "=============================\n"
    "🌿 AURA’S CORE PURPOSE\n"
    "=============================\n"
    "- Guide users toward healthier habits using compassion and clarity.\n"
    "- Offer realistic, sustainable advice — never overwhelming or judgmental.\n"
    "- Encourage emotional balance, mindfulness, and self-awareness.\n"
    "- Support users' confidence, motivation, and consistency.\n"
    "- Prioritize psychological and physical safety above all.\n\n"

    "=============================\n"
    "📌 USER CONTEXT\n"
    "=============================\n"
    "Profile Summary: " + str(profile_info) + "\n"
    "Tone Guide: " + str(tone_instructions) + "\n\n"

    "AURA uses this profile to adjust tone, complexity, motivation level, and recommendations.\n\n"

    "=============================\n"
    "✨ AURA'S COMMUNICATION STYLE\n"
    "=============================\n"
    "AURA must always:\n"
    "- Speak with empathy, warmth, and emotional intelligence.\n"
    "- Validate the user's feelings before offering any advice.\n"
    "- Use simple, digestible, friendly, clear language.\n"
    "- Provide short, actionable steps (never long lists of overwhelming tasks).\n"
    "- Keep the tone optimistic, encouraging, and uplifting.\n"
    "- Sound human-like, not robotic.\n"
    "- Maintain psychological safety: no pressure, no guilt, no moralizing.\n\n"

    "AURA avoids:\n"
    "- Medical diagnosis, treatment, or speculation.\n"
    "- Fear-based language, shame, or perfectionism.\n"
    "- Complex scientific jargon without explanation.\n\n"

    "=============================\n"
    "🌱 LIFESTYLE & HEALTH GUIDANCE\n"
    "=============================\n"
    "When giving general health tips:\n"
    "- Focus on daily habits: hydration, sleep hygiene, mindful breaks, gentle movement.\n"
    "- Offer small improvements rather than big lifestyle overhauls.\n"
    "- Encourage balance, not restriction.\n"
    "- Promote mindful eating, stress reduction, and regular sleep schedules.\n"
    "- Keep all recommendations non-medical, general, and safe.\n\n"

    "=============================\n"
    "💪 EXERCISE GUIDANCE\n"
    "=============================\n"
    "When giving exercise advice:\n"
    "- Tailor intensity to user activity level.\n"
    "- Start with simple, safe routines such as walking, stretching, or bodyweight exercises.\n"
    "- Provide warm-up and cool-down suggestions when appropriate.\n"
    "- Encourage gradual progression and listening to the body's signals.\n"
    "- For low-energy days: suggest gentle options like mobility work, light stretching, "
    "or a 5-minute walk.\n\n"

    "=============================\n"
    "🧘 EMOTIONAL & MENTAL WELLNESS SUPPORT\n"
    "=============================\n"
    "AURA should:\n"
    "- Offer grounding exercises (breathing, counting, sensory grounding).\n"
    "- Suggest journaling prompts to explore thoughts safely.\n"
    "- Encourage short mindfulness or reflection moments.\n"
    "- Normalize emotional struggle and reduce self-judgment.\n"
    "- Provide small mood-lifting ideas (sunlight, movement, micro-breaks, gratitude).\n\n"

    "AURA should NOT:\n"
    "- Give clinical mental health assessments.\n"
    "- Provide crisis counseling.\n"
    "- Claim to treat depression, anxiety, or disorders.\n\n"

    "=============================\n"
    "🥗 NUTRITION GUIDANCE\n"
    "=============================\n"
    "AURA should:\n"
    "- Promote balanced meals with protein, veggies, whole foods, fruits, and hydration.\n"
    "- Give simple suggestions, not strict diet rules.\n"
    "- Encourage mindful eating and awareness of hunger cues.\n"
    "- Normalize flexibility (treats, cravings, cultural foods).\n\n"

    "AURA should NOT:\n"
    "- Provide calorie numbers, macros, or diet plans.\n"
    "- Give medical or clinical nutrition advice.\n\n"

    "=============================\n"
    "🛡 SAFETY REQUIREMENTS\n"
    "=============================\n"
    + str(safety_clause) + "\n\n"

    "=============================\n"
    "🌟 OVERALL BEHAVIOR\n"
    "=============================\n"
    "In every response, AURA should:\n"
    "- Be gentle, uplifting, and encouraging.\n"
    "- Provide short, practical, evidence-backed suggestions.\n"
    "- Adapt tone and guidance to the user's emotional state.\n"
    "- Prioritize safety, emotional validation, and empowerment.\n"
    "- Keep the response helpful but not overly long.\n"
    "- End with encouragement or reassurance when appropriate.\n\n"

    "AURA = Empathy + Clarity + Motivation + Evidence-Based Lifestyle Guidance.\n"
)

    # --- Build message history for context ---
    history_msgs = []
    if hasattr(st.session_state, "chat_history"):
        for msg in st.session_state.chat_history[-5:]:
            role = "model" if msg.get('role') == 'assistant' else 'user'
            history_msgs.append({"role": role, "parts": [msg.get('content', '')]})

    # --- Try multiple free Gemini models with fallback ---
    # List of free Gemini models to try in order of preference
    free_models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite", 
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    
    last_error = None
    last_model = None
    for model_name in free_models:
        try:
            model = genai.GenerativeModel(model_name)
            chat = model.start_chat(history=history_msgs)

            prompt = system_prompt + "\n\nUser: " + user_input
            response = chat.send_message(prompt)

            # Extract and return the model text
            return response.text.strip() if hasattr(response, "text") else str(response)
            
        except Exception as e:
            last_error = e
            last_model = model_name
            # Continue to next model if this one fails
            continue
    
    # If all models failed, return error message
    return f"⚠️ All Gemini models failed. Tried: {', '.join(free_models)}. Last error ({last_model}): {str(last_error)}"
# Login and authentication functions
def authenticate_user(username, password):
    """Authenticate against MySQL users table"""
    # Ensure database is initialized before use
    ensure_database_initialized()
    conn = get_database_connection()
    if not conn:
        demo_users = {
            'admin': 'admin123',
            'user': 'user123',
            'demo': 'demo123'
        }
        if username in demo_users and demo_users[username] == password:
            return True, username
        return False, None
    
    try:
        cursor = conn.cursor()
        cursor.execute("USE wellness_db")
        
        password_hash = hash_password(password)
        cursor.execute(
            "SELECT username FROM users WHERE username=%s AND password_hash=%s",
            (username, password_hash)
        )
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if row:
            return True, row[0]
        
        demo_users = {
            'admin': 'admin123',
            'user': 'user123',
            'demo': 'demo123'
        }
        if username in demo_users and demo_users[username] == password:
            return True, username
        return False, None
        
    except Error:
        try:
            conn.close()
        except:
            pass
        return False, None

def register_user(username, password):
    """Register a new user in MySQL users table"""
    if not username or not password:
        return False, "Username and password are required"
    
    # Ensure database is initialized before use
    ensure_database_initialized()
    conn = get_database_connection()
    if not conn:
        return False, "Database not available"
    
    try:
        cursor = conn.cursor()
        cursor.execute("USE wellness_db")
        
        password_hash = hash_password(password)
        
        cursor.execute(
            "INSERT INTO users (username, password, password_hash) VALUES (%s, %s, %s)",
            (username, password, password_hash)
        )
        
        cursor.close()
        conn.close()
        return True, "Account created successfully! Please login to continue."
        
    except mysql.connector.IntegrityError:
        try:
            conn.close()
        except:
            pass
        return False, "Username already exists"
    except Error as e:
        try:
            conn.close()
        except:
            pass
        return False, "Registration error: " + str(e)

def save_user_profile(username, age, height, weight, gender, mode, physical_activity=None, stress_level=None):
    """Save user profile data to database"""
    # Ensure database is initialized before use
    ensure_database_initialized()
    conn = get_database_connection()
    if not conn:
        return False, "Database not available"
    
    try:
        cursor = conn.cursor()
        cursor.execute("USE wellness_db")
        
        if mode and len(mode) > 100:
            mode = mode[:100]
        
        cursor.execute(
            "UPDATE users SET age=%s, height=%s, weight=%s, gender=%s, mode=%s, physical_activity_level=%s, stress_level=%s WHERE username=%s",
            (age, height, weight, gender, mode, physical_activity, stress_level, username)
        )
        
        cursor.close()
        conn.close()
        return True, "Profile saved successfully!"
        
    except Error as e:
        try:
            conn.close()
        except:
            pass
        if "Data too long" in str(e):
            return False, "Data too long for database column. Please try shorter text."
        else:
            return False, "Error saving profile: " + str(e)

def get_user_profile(username):
    """Get user profile data from database"""
    # Ensure database is initialized before use
    ensure_database_initialized()
    conn = get_database_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("USE wellness_db")
        
        cursor.execute(
            "SELECT age, height, weight, gender, mode, physical_activity_level, stress_level FROM users WHERE username=%s",
            (username,)
        )
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if row:
            return {
                'age': safe_convert_db_value(row[0], int),
                'height': safe_convert_db_value(row[1], float),
                'weight': safe_convert_db_value(row[2], float),
                'gender': row[3],
                'mode': row[4],
                'physical_activity_level': row[5],
                'stress_level': row[6]
            }
        return None
        
    except Error:
        try:
            conn.close()
        except:
            pass
        return None

def login_user(username, password):
    """Login user with authentication"""
    success, user = authenticate_user(username, password)
    if success:
        st.session_state.chat_history = []
        
        st.session_state.login_state.update({
            'is_logged_in': True,
            'is_guest': False,
            'username': user,
            'user_type': 'registered'
        })
        
        profile = get_user_profile(user)
        if profile and profile['age']:
            bmi = calculate_bmi(profile['weight'], profile['height'])
            bmi_category = "Underweight" if bmi < 18.5 else "Normal" if bmi < 25 else "Overweight" if bmi < 30 else "Obese"
            target_calories = calculate_target_calories(profile['weight'], profile['height'], profile['age'], profile['mode'], profile['gender'])
            
            st.session_state.user_data.update({
                'age': profile['age'],
                'gender': profile['gender'],
                'weight': profile['weight'],
                'height': profile['height'],
                'bmi': bmi,
                'bmi_category': bmi_category,
                'mode': profile['mode'],
                'target_calories': target_calories,
                'physical_activity_level': profile.get('physical_activity_level', 'Moderate'),
                'stress_level': profile.get('stress_level', 'Moderate'),
                'logged_in': True
            })
        
        return True, "Welcome back, " + str(user) + "!"
    return False, "Invalid username or password"

def login_guest():
    """Login as guest user"""
    st.session_state.chat_history = []
    
    st.session_state.login_state.update({
        'is_logged_in': True,
        'is_guest': True,
        'username': 'Guest',
        'user_type': 'guest'
    })
    return True, "Welcome as Guest! You can explore the app with limited features."

def logout_user():
    """Logout current user"""
    st.session_state.chat_history = []
    
    st.session_state.login_state.update({
        'is_logged_in': False,
        'is_guest': False,
        'username': None,
        'user_type': None
    })
    st.session_state.user_data.update({
        'age': None,
        'weight': None,
        'height': None,
        'mode': None,
        'logged_in': False,
        'bmi': None,
        'target_calories': None
    })
    return "Logged out successfully!"

def is_guest_user():
    """Check if current user is guest"""
    return st.session_state.login_state.get('is_guest', False)

def is_logged_in():
    """Check if user is logged in"""
    return st.session_state.login_state.get('is_logged_in', False)

def check_user_change():
    """Check if user has changed and clear chat history if needed"""
    current_username = st.session_state.login_state.get('username')
    if st.session_state.current_user != current_username:
        st.session_state.chat_history = []
        st.session_state.current_user = current_username

def check_achievements():
    """Check and award achievements based on user activity"""
    badges = []
    
    # Check workout achievements
    if st.session_state.achievements['total_workouts'] >= 1:
        badges.append("🏃 First Workout")
    if st.session_state.achievements['total_workouts'] >= 10:
        badges.append("💪 Workout Warrior")
    if st.session_state.achievements['total_workouts'] >= 50:
        badges.append("🏆 Fitness Champion")
    
    # Check streak achievements
    if st.session_state.achievements['streak_days'] >= 3:
        badges.append("🔥 3-Day Streak")
    if st.session_state.achievements['streak_days'] >= 7:
        badges.append("⭐ Week Warrior")
    if st.session_state.achievements['streak_days'] >= 30:
        badges.append("👑 Month Master")
    
    # Check sleep tracking
    if len(st.session_state.sleep_data) >= 7:
        badges.append("😴 Sleep Tracker")
    
    # Check mood tracking
    if len(st.session_state.mood_history) >= 7:
        badges.append("😊 Mood Master")
    
    # Check meal logging
    if len(st.session_state.meal_log) >= 10:
        badges.append("🍎 Nutrition Ninja")
    
    st.session_state.achievements['badges'] = badges
    return badges

def calculate_health_score():
    """Calculate overall health score based on recent activity"""
    score = 0
    factors = []
    
    # Sleep score (30 points)
    if st.session_state.sleep_data:
        recent_sleep = st.session_state.sleep_data[-7:] if len(st.session_state.sleep_data) >= 7 else st.session_state.sleep_data
        avg_sleep = sum(s['duration'] for s in recent_sleep) / len(recent_sleep)
        if 7 <= avg_sleep <= 9:
            sleep_score = 30
        elif 6 <= avg_sleep <= 10:
            sleep_score = 20
        else:
            sleep_score = 10
        score += sleep_score
        factors.append(f"Sleep: {sleep_score}/30")
    
    # Exercise score (25 points)
    if st.session_state.health_metrics['exercise_minutes'] > 0:
        if st.session_state.health_metrics['exercise_minutes'] >= 30:
            exercise_score = 25
        else:
            exercise_score = (st.session_state.health_metrics['exercise_minutes'] / 30) * 25
        score += exercise_score
        factors.append(f"Exercise: {exercise_score:.0f}/25")
    
    # Mood score (20 points)
    if st.session_state.mood_history:
        recent_moods = st.session_state.mood_history[-7:]
        avg_mood = sum(m['polarity'] for m in recent_moods) / len(recent_moods)
        mood_score = max(0, min(20, (avg_mood + 1) * 10))
        score += mood_score
        factors.append(f"Mood: {mood_score:.0f}/20")
    
    # Consistency score (25 points)
    consistency_score = min(25, st.session_state.achievements['streak_days'] * 3)
    score += consistency_score
    factors.append(f"Consistency: {consistency_score}/25")
    
    return min(100, score), factors

# Sidebar - Modern Design
st.sidebar.markdown(f"""
    <div style="
        text-align: center;
        padding: 1.5rem 0;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    ">
        <h1 style="
            font-size: 1.8rem;
            margin: 0;
            background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        ">🌟 AI Wellness Guardian</h1>
        <p style="
            color: {MUTED};
            font-size: 0.85rem;
            margin: 0.5rem 0 0 0;
        ">Your smart health companion</p>
        <span class='badge glow' style="margin-top: 0.5rem; display: inline-block;">v1.0</span>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# User Info Section
if is_logged_in():
    username = st.session_state.login_state.get('username', 'User')
    user_type = st.session_state.login_state.get('user_type', '')
    
    if is_guest_user():
        st.sidebar.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(91,141,239,0.15) 0%, rgba(78,205,196,0.1) 100%);
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1rem;
            border: 1px solid rgba(255,255,255,0.1);
        ">
            <div style="font-size: 1.1rem; font-weight: 600; color: {TEXT}; margin-bottom: 0.3rem;">👤 Guest User</div>
            <div style="font-size: 0.85rem; color: {MUTED};">Limited features available</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(91,141,239,0.15) 0%, rgba(78,205,196,0.1) 100%);
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1rem;
            border: 1px solid rgba(255,255,255,0.1);
        ">
            <div style="font-size: 1.1rem; font-weight: 600; color: {TEXT}; margin-bottom: 0.3rem;">👤 {username}</div>
            <div style="font-size: 0.85rem; color: {MUTED};">{user_type.title()} Account</div>
        </div>
        """, unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        logout_user()
        st.rerun()
else:
    st.sidebar.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(245,166,35,0.15) 0%, rgba(232,93,117,0.1) 100%);
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.1);
    ">
        <div style="font-size: 1rem; font-weight: 600; color: {TEXT}; margin-bottom: 0.3rem;">🔒 Login Required</div>
        <div style="font-size: 0.85rem; color: {MUTED};">Please login to access all features</div>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")

# Navigation with Icons
page_icons = {
    "Home": "🏠",
    "Login": "🔐",
    "Profile Registration": "👤",
    "Daily Tracker": "📊",
    "Health Recommendations": "💡",
    "Meal Logger": "🍽️",
    "Progress & Goals": "🎯",
    "Mood Detection": "😊",
    "Sleep Analysis": "💤",
    "Dashboard": "📈",
    "AI Fitness Trainer": "💪",
    "Health Journal": "📝",
    "Fake News Detection": "🔍",
    "Chatbot Assistant": "🤖"
}

if is_logged_in():
    pages = [
        "Home",
        "Profile Registration",
        "Daily Tracker",
        "Health Recommendations", 
        "Meal Logger",
        "Progress & Goals",
        "Mood Detection",
        "Sleep Analysis",
        "Dashboard",
        "AI Fitness Trainer",
        "Health Journal",
        "Fake News Detection",
        "Chatbot Assistant"
    ]
else:
    pages = [
        "Home",
        "Login",
        "Profile Registration",
        "Daily Tracker",
        "Health Recommendations",
        "Meal Logger",
        "Progress & Goals",
        "Mood Detection", 
        "Sleep Analysis",
        "Dashboard",
        "AI Fitness Trainer",
        "Health Journal",
        "Fake News Detection",
        "Chatbot Assistant"
    ]

# Create navigation with icons - More robust handling
try:
    # Initialize session state for page tracking
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    
    pages_with_icons = [f"{page_icons.get(page, '📄')} {page}" for page in pages]
    
    # Use index to track selection properly
    if 'selected_page_index' not in st.session_state:
        # Try to find current page in list
        try:
            current_index = pages.index(st.session_state.current_page)
        except (ValueError, IndexError):
            current_index = 0
        st.session_state.selected_page_index = current_index
    
    selected_with_icon = st.sidebar.selectbox(
        "📍 Navigate", 
        pages_with_icons,
        index=st.session_state.selected_page_index,
        key="nav_selectbox"
    )
    
    # Update index
    try:
        if selected_with_icon in pages_with_icons:
            st.session_state.selected_page_index = pages_with_icons.index(selected_with_icon)
    except (ValueError, IndexError):
        st.session_state.selected_page_index = 0
    
    # Extract page name from selected option - handle both formats
    if selected_with_icon:
        if " " in selected_with_icon:
            # Remove icon and get page name
            parts = selected_with_icon.split(" ", 1)
            if len(parts) > 1:
                page = parts[1].strip()
            else:
                page = selected_with_icon.strip()
        else:
            page = selected_with_icon.strip()
    else:
        page = st.session_state.current_page if st.session_state.current_page in pages else "Home"
    
    # Fallback to ensure page is valid
    if page not in pages:
        # Try to find matching page without icon
        found = False
        for p in pages:
            if p in selected_with_icon or (selected_with_icon and selected_with_icon in p):
                page = p
                found = True
                break
        if not found:
            page = pages[0] if pages else "Home"
    
    # Update session state
    st.session_state.current_page = page
            
except Exception as e:
    # Fallback to simple navigation if there's an error
    try:
        if 'current_page' in st.session_state and st.session_state.current_page in pages:
            page = st.session_state.current_page
        else:
            page = st.sidebar.selectbox("Navigate", pages) if pages else "Home"
            st.session_state.current_page = page
    except:
        page = "Home"
        st.session_state.current_page = page

# Page Routing with Error Handling
# Login Page
if page == "Login":
    st.markdown(f"""
    <style>
    /* Enhanced Login Container with Centered Design */
    .login-container {{
        background: transparent;
        padding: 3rem 1rem;
        min-height: calc(100vh - 100px);
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        overflow: hidden;
    }}
    
    /* Animated Background Elements */
    .login-container::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(91,141,239,0.1) 0%, transparent 70%);
        animation: rotate-glow 20s linear infinite;
        pointer-events: none;
    }}
    
    .login-container::after {{
        content: '';
        position: absolute;
        bottom: -30%;
        right: -30%;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle, rgba(78,205,196,0.08) 0%, transparent 70%);
        animation: rotate-glow 25s linear infinite reverse;
        pointer-events: none;
    }}
    
    /* Modern Login Form with Unique Shape */
    .login-form {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.95) 0%, 
            rgba(42, 49, 69, 0.9) 100%);
        padding: 3.5rem 3rem;
        border-radius: 28px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5),
                    0 0 0 1px rgba(255,255,255,0.1),
                    inset 0 1px 0 rgba(255,255,255,0.15),
                    0 0 80px rgba(91,141,239,0.15);
        border: 1px solid rgba(255,255,255,0.12);
        max-width: 480px;
        width: 100%;
        position: relative;
        z-index: 1;
        backdrop-filter: blur(30px) saturate(180%);
        -webkit-backdrop-filter: blur(30px) saturate(180%);
        animation: login-float 6s ease-in-out infinite;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .login-form:hover {{
        transform: translateY(-5px);
        box-shadow: 0 25px 70px rgba(0,0,0,0.6),
                    0 0 0 1px rgba(91,141,239,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.2),
                    0 0 100px rgba(91,141,239,0.25);
    }}
    
    @keyframes login-float {{
        0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
        50% {{ transform: translateY(-8px) rotate(0.5deg); }}
    }}
    
    /* Decorative Top Accent */
    .login-form::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 120px;
        height: 4px;
        background: linear-gradient(90deg, 
            transparent, 
            {PRIMARY} 20%, 
            {ACCENT} 50%, 
            {PRIMARY} 80%, 
            transparent);
        border-radius: 0 0 4px 4px;
        box-shadow: 0 4px 20px rgba(91,141,239,0.5);
    }}
    
    .login-header {{
        text-align: center;
        margin-bottom: 2.5rem;
        position: relative;
    }}
    
    .login-header::after {{
        content: '';
        position: absolute;
        bottom: -1rem;
        left: 50%;
        transform: translateX(-50%);
        width: 60px;
        height: 3px;
        background: linear-gradient(90deg, {PRIMARY}, {ACCENT});
        border-radius: 2px;
    }}
    
    .login-title {{
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 50%, {PRIMARY} 100%);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.75rem;
        letter-spacing: -0.5px;
        animation: gradient-shift 3s ease infinite;
        position: relative;
    }}
    
    .login-subtitle {{
        color: {MUTED};
        font-size: 1.05rem;
        font-weight: 400;
        margin-top: 0.5rem;
        letter-spacing: 0.3px;
    }}
    
    /* Enhanced Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.8) 0%, 
            rgba(42, 49, 69, 0.6) 100%);
        backdrop-filter: blur(20px) saturate(180%);
        border-radius: 16px;
        padding: 6px;
        margin-bottom: 2.5rem;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.1);
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        border-radius: 12px;
        padding: 0.9rem 2rem;
        font-weight: 600;
        color: {MUTED};
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        font-size: 0.95rem;
        position: relative;
        overflow: hidden;
    }}
    
    .stTabs [data-baseweb="tab"]::before {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 0;
        height: 2px;
        background: {PRIMARY};
        transition: width 0.3s ease;
    }}
    
    .stTabs [data-baseweb="tab"]:hover::before {{
        width: 60%;
    }}
    
    .stTabs [data-baseweb="tab"]:hover {{
        color: {TEXT};
        background: rgba(91,141,239,0.1);
    }}
    
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        color: white;
        box-shadow: 0 6px 25px rgba(91,141,239,0.4),
                    inset 0 1px 0 rgba(255,255,255,0.2);
        transform: scale(1.02);
    }}
    
    .stTabs [aria-selected="true"]::before {{
        width: 80%;
    }}
    
    /* Enhanced Input Fields */
    .stTextInput > div > div > input,
    .stTextInput > div > div > input[type="password"] {{
        background: linear-gradient(135deg, 
            rgba(37, 43, 61, 0.9) 0%, 
            rgba(42, 49, 69, 0.7) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 14px;
        padding: 0.9rem 1.2rem;
        font-size: 0.95rem;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        color: {TEXT};
        box-shadow: 0 4px 15px rgba(0,0,0,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.05);
    }}
    
    .stTextInput > div > div > input:hover {{
        border-color: rgba(91,141,239,0.4);
        box-shadow: 0 6px 20px rgba(91,141,239,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.1);
        transform: translateY(-1px);
    }}
    
    .stTextInput > div > div > input:focus {{
        border-color: {PRIMARY};
        box-shadow: 0 0 0 4px rgba(91,141,239,0.25),
                    0 8px 25px rgba(91,141,239,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.15);
        background: linear-gradient(135deg, 
            rgba(42, 49, 69, 0.95) 0%, 
            rgba(37, 43, 61, 0.8) 100%);
        transform: translateY(-2px) scale(1.01);
        outline: none;
    }}
    
    .stTextInput > div > div > input::placeholder {{
        color: {MUTED};
        opacity: 0.7;
    }}
    
    /* Form Card Enhancement */
    .login-form .card {{
        background: rgba(30, 35, 50, 0.4);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 2rem;
        margin-top: 1rem;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }}
    
    .login-form .card:hover {{
        background: rgba(30, 35, 50, 0.5);
        border-color: rgba(91,141,239,0.2);
    }}
    
    /* Success/Error Messages in Login */
    .login-form .stSuccess,
    .login-form .stError,
    .login-form .stInfo {{
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1rem;
        animation: slideInDown 0.5s ease-out;
    }}
    
    @keyframes slideInDown {{
        from {{
            opacity: 0;
            transform: translateY(-20px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # Centered Login Form with Better Layout
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-container">
            <div class="login-form">
                <div class="login-header">
                    <div style="font-size: 4rem; margin-bottom: 1rem; animation: float 3s ease-in-out infinite;">🌟</div>
                    <div class="badge glow" style="margin-bottom: 1rem;">SECURE LOGIN</div>
                    <div class="login-title">AI Wellness Guardian</div>
                    <div class="login-subtitle">Sign in to access your personalized health dashboard</div>
                </div>
        """, unsafe_allow_html=True)
    
        tab1, tab2 = st.tabs(["🔐 Sign In", "✨ Sign Up"])
        
        with tab1:
            st.markdown('<div class="card" style="background: rgba(30, 35, 50, 0.4); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 2rem;">', unsafe_allow_html=True)
            st.markdown("### <span style='color: #ffffff;'>Sign In to Your Account</span>", unsafe_allow_html=True)
            st.markdown("<p style='color: #9CA5B8; margin-bottom: 1.5rem;'>Enter your credentials to access your personalized health dashboard</p>", unsafe_allow_html=True)
            
            with st.form("login_form"):
                username = st.text_input("👤 Username", placeholder="Enter your username", key="login_username")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="login_password")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                col_login, col_guest = st.columns(2)
                
                with col_login:
                    login_submit = st.form_submit_button("🚀 Login", use_container_width=True, type="primary")
                
                with col_guest:
                    guest_submit = st.form_submit_button("👤 Guest Access", use_container_width=True, type="secondary")
                
                if login_submit:
                    if username and password:
                        with st.spinner("🔐 Authenticating..."):
                            time.sleep(1.5)
                        success, message = login_user(username, password)
                        if success:
                            st.success(f"🎉 {message}")
                            st.balloons()
                            profile = get_user_profile(username)
                            if profile and profile['age']:
                                st.markdown("""
                                <script>
                                setTimeout(function() {
                                    window.location.href = window.location.href.split('?')[0] + '?page=Dashboard';
                                }, 2000);
                                </script>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <script>
                                setTimeout(function() {
                                    window.location.href = window.location.href.split('?')[0] + '?page=Profile Registration';
                                }, 2000);
                                </script>
                                """, unsafe_allow_html=True)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.error("⚠️ Please enter both username and password")
                
                if guest_submit:
                    with st.spinner("👤 Setting up guest session..."):
                        time.sleep(1)
                    success, message = login_guest()
                    if success:
                        st.success(f"🎉 {message}")
                        st.balloons()
                        st.markdown("""
                        <script>
                        setTimeout(function() {
                            window.location.href = window.location.href.split('?')[0] + '?page=Home';
                        }, 2000);
                        </script>
                        """, unsafe_allow_html=True)
                        time.sleep(2)
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab2:
            st.markdown('<div class="card" style="background: rgba(30, 35, 50, 0.4); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 2rem;">', unsafe_allow_html=True)
            st.markdown("### <span style='color: #ffffff;'>Create Your Account</span>", unsafe_allow_html=True)
            st.markdown("<p style='color: #9CA5B8; margin-bottom: 1.5rem;'>Join us and start your wellness journey today</p>", unsafe_allow_html=True)
            
            with st.form("register_form"):
                new_username = st.text_input("👤 Choose Username", placeholder="Pick a unique username", key="register_username")
                new_password = st.text_input("🔒 Create Password", type="password", placeholder="Choose a strong password", key="register_password")
                confirm_password = st.text_input("🔒 Confirm Password", type="password", placeholder="Re-enter your password", key="register_confirm")
                create_btn = st.form_submit_button("✨ Create Account", use_container_width=True, type="primary")
                
                if create_btn:
                    if not new_username or not new_password or not confirm_password:
                        st.error("⚠️ Please fill in all fields")
                    elif new_password != confirm_password:
                        st.error("⚠️ Passwords do not match")
                    else:
                        ok, msg = register_user(new_username, new_password)
                        if ok:
                            st.success(f"✅ {msg}")
                            st.info("💡 Please switch to the Login tab to sign in with your new account.")
                        else:
                            st.error(f"❌ {msg}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("""
                </div>
        </div>
        """, unsafe_allow_html=True)

# Home Page
elif page == "Home":
    st.markdown('<div class="page-container">', unsafe_allow_html=True)
    
    if is_logged_in():
        username = st.session_state.login_state.get('username', 'User')
        if is_guest_user():
            st.markdown(f"""
            <div style="text-align: center; margin: 2rem 0; padding: 2rem;">
                <h1 style="font-size: 2.5rem; margin-bottom: 1rem;">Welcome, {username}! 👤</h1>
                <div class="badge" style="margin: 1rem auto; display: inline-block;">GUEST MODE</div>
            </div>
            """, unsafe_allow_html=True)
            st.info("💡 You're browsing as a guest. Login for full features and personalized recommendations!")
        else:
            st.markdown(f"""
            <div style="text-align: center; margin: 2rem 0; padding: 2rem;">
                <div style="font-size: 4rem; animation: float 3s ease-in-out infinite; margin-bottom: 1rem;">🌟</div>
                <h1 style="font-size: 2.8rem; margin-bottom: 1rem; background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    Welcome back, {username}!
                </h1>
                <p style="font-size: 1.3rem; color: {MUTED}; margin-top: 1rem;">
                    Your personalized health journey continues here
                </p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align: center; margin: 2rem 0; padding: 3rem 2rem; background: linear-gradient(135deg, rgba(91,141,239,0.2) 0%, rgba(78,205,196,0.15) 100%); border-radius: 24px; border: 1px solid rgba(91,141,239,0.3); box-shadow: 0 12px 40px rgba(91,141,239,0.2);">
            <div style="font-size: 4rem; margin-bottom: 1.5rem; animation: pulse 2s infinite;">🌟</div>
            <h1 style="font-size: 2.5rem; margin-bottom: 1rem; color: white;">Ready to Start Your Health Journey?</h1>
            <p style="font-size: 1.2rem; color: {MUTED}; margin-bottom: 2rem; max-width: 600px; margin-left: auto; margin-right: auto;">
                Login or try as guest to unlock personalized health recommendations powered by AI
            </p>
            <div style="font-size: 3rem; animation: float 3s ease-in-out infinite;">🚀</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Hero Section with Better Layout
    colA, colB = st.columns([1.2, 1])
    with colA:
        st.markdown('<div class="card hero interactive-card">', unsafe_allow_html=True)
        st.markdown("<div class='badge glow' style='margin-bottom: 1rem;'>AI-POWERED HEALTH</div>", unsafe_allow_html=True)
        st.markdown("<h2 style='margin-bottom: 1rem;'>Your daily companion for a stronger body and calmer mind</h2>", unsafe_allow_html=True)
        st.markdown("<p class='muted' style='font-size: 1.05rem; line-height: 1.6;'>Personalized recommendations for diet, exercise, sleep and mood—beautifully presented with smart AI insights.</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with colB:
        hero_anim = get_hero_animation()
        if st_lottie and hero_anim:
            st.markdown('<div class="card interactive-card" style="display: flex; align-items: center; justify-content: center; min-height: 300px;">', unsafe_allow_html=True)
            st_lottie(hero_anim, height=280, key="hero")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card interactive-card" style="display: flex; align-items: center; justify-content: center; min-height: 300px; background: linear-gradient(135deg, rgba(91,141,239,0.1) 0%, rgba(78,205,196,0.1) 100%);">', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="text-align: center;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">✨</div>
                <p style="color: {MUTED};">Animation unavailable</p>
                <p style="color: {MUTED}; font-size: 0.85rem;">Install streamlit-lottie to enable</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # Key Features with Enhanced Layout
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom: 1.5rem; text-align: center;'>🌟 Key Features</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class='metric interactive-card'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🍎</div>
            <div class='label'>Personal Plans</div>
            <div class='value'>Diet • Exercise</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class='metric interactive-card'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>💚</div>
            <div class='label'>Wellbeing</div>
            <div class='value'>Mood • Sleep</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class='metric interactive-card'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🛡️</div>
            <div class='label'>Safety</div>
            <div class='value'>Fake News</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Usage Scenario with Better Formatting
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom: 1.5rem;'>📋 How It Works</h2>", unsafe_allow_html=True)
    st.markdown("""
    <div style="padding: 1rem; background: rgba(30, 35, 50, 0.4); border-radius: 12px; border-left: 4px solid #5B8DEF;">
        <ul style="list-style: none; padding: 0; margin: 0;">
            <li style="padding: 0.75rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                <span style="color: #5B8DEF; font-weight: 600; margin-right: 0.5rem;">1.</span>
                Register your profile and select your fitness goal (Bulk or Cutting Mode)
            </li>
            <li style="padding: 0.75rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                <span style="color: #5B8DEF; font-weight: 600; margin-right: 0.5rem;">2.</span>
                Get personalized diet and exercise plans tailored to your needs
            </li>
            <li style="padding: 0.75rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                <span style="color: #5B8DEF; font-weight: 600; margin-right: 0.5rem;">3.</span>
                Track sleep patterns and receive AI-powered solutions for better rest
            </li>
            <li style="padding: 0.75rem 0;">
                <span style="color: #5B8DEF; font-weight: 600; margin-right: 0.5rem;">4.</span>
                Verify health news articles with our fake news detection system
            </li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Profile Registration Page
elif page == "Profile Registration":
    st.title("Profile Registration 👤")
    
    if not is_logged_in():
        st.warning("Please login first to register your profile.")
        st.info("You can login as a guest to explore the app, but full features require registration.")
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form(key="registration_form"):
            st.subheader("Enter Your Basic Information")
            col1, col2 = st.columns(2)
            
            with col1:
                age = st.number_input("Age", min_value=18, max_value=100, step=1)
                gender = st.selectbox("Gender", ["Male", "Female"])
                weight = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, step=0.1)
                height = st.number_input("Height (cm)", min_value=100.0, max_value=250.0, step=0.1)
            
            with col2:
                mode = st.radio("Choose Your Goal", ["Bulk Mode (Weight Gain)", "Cutting Mode (Weight Loss)"])
                physical_activity = st.select_slider("Physical Activity Level", 
                                                   options=["Sedentary", "Light", "Moderate", "Active", "Very Active"], 
                                                   value="Moderate")
                stress_level = st.select_slider("Stress Level", 
                                              options=["Very Low", "Low", "Moderate", "High", "Very High"], 
                                              value="Moderate")
            
            submit = st.form_submit_button("Register Profile", use_container_width=True)
            
            if submit:
                bmi = calculate_bmi(weight, height)
                bmi_category = "Underweight" if bmi < 18.5 else "Normal" if bmi < 25 else "Overweight" if bmi < 30 else "Obese"
                target_calories = calculate_target_calories(weight, height, age, mode, gender)
                
                username = st.session_state.login_state.get('username')
                if username and not is_guest_user():
                    success, message = save_user_profile(
                        username, age, height, weight, gender, mode, physical_activity, stress_level
                    )
                    if success:
                        st.success(f"Profile saved to database! 🎉")
                    else:
                        st.error(f"Database error: {message}")
                
                st.session_state.user_data.update({
                    'age': age,
                    'gender': gender,
                    'weight': weight,
                    'height': height,
                    'bmi': bmi,
                    'bmi_category': bmi_category,
                    'mode': mode,
                    'target_calories': target_calories,
                    'physical_activity_level': physical_activity,
                    'stress_level': stress_level,
                    'logged_in': True
                })
                st.success("Profile registered successfully! 🎉")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.user_data['logged_in']:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📊 Personal Info")
            st.write(f"**Age:** {st.session_state.user_data['age']} years")
            st.write(f"**Gender:** {st.session_state.user_data['gender']}")
            st.write(f"**Weight:** {st.session_state.user_data['weight']} kg")
            st.write(f"**Height:** {st.session_state.user_data['height']} cm")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📈 Health Metrics")
            st.write(f"**BMI:** {st.session_state.user_data['bmi']:.1f} ({st.session_state.user_data['bmi_category']})")
            st.write(f"**Target Calories:** {st.session_state.user_data['target_calories']} per day")
            st.write(f"**Goal:** {st.session_state.user_data['mode']}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("🎯 Lifestyle")
            st.write(f"**Activity Level:** {st.session_state.user_data['physical_activity_level']}")
            st.write(f"**Stress Level:** {st.session_state.user_data['stress_level']}")
            st.write(f"**Registration:** {datetime.now().strftime('%Y-%m-%d')}")
            st.markdown('</div>', unsafe_allow_html=True)

# Daily Tracker Page
elif page == "Daily Tracker":
    if not is_logged_in():
        st.warning("Please login first to access daily tracker.")
    else:
        st.title("Daily Tracker 📊")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader(f"📅 Today's Progress - {today}")
        
        # Quick logging section
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.write("**💧 Water Intake**")
            water_glasses = st.number_input("Glasses", min_value=0, max_value=20, value=st.session_state.health_metrics['water_intake'], key="water")
            st.session_state.health_metrics['water_intake'] = water_glasses
            water_progress = min(100, (water_glasses / st.session_state.daily_goals['water_goal']) * 100)
            st.progress(water_progress / 100)
            st.caption(f"{water_glasses}/{st.session_state.daily_goals['water_goal']} glasses")
        
        with col2:
            st.write("**🍽️ Calories**")
            calories = st.number_input("Calories", min_value=0, max_value=5000, value=int(st.session_state.health_metrics['daily_calories']), key="calories")
            st.session_state.health_metrics['daily_calories'] = calories
            cal_goal = st.session_state.user_data.get('target_calories', 2000)
            cal_progress = min(100, (calories / cal_goal) * 100)
            st.progress(cal_progress / 100)
            st.caption(f"{calories}/{cal_goal} kcal")
        
        with col3:
            st.write("**💪 Exercise**")
            exercise_min = st.number_input("Minutes", min_value=0, max_value=300, value=st.session_state.health_metrics['exercise_minutes'], key="exercise")
            st.session_state.health_metrics['exercise_minutes'] = exercise_min
            ex_progress = min(100, (exercise_min / st.session_state.daily_goals['exercise_goal']) * 100)
            st.progress(ex_progress / 100)
            st.caption(f"{exercise_min}/{st.session_state.daily_goals['exercise_goal']} min")
        
        with col4:
            st.write("**😊 Mood**")
            mood_select = st.select_slider("How are you?", options=["😢", "😕", "😐", "🙂", "😄"], value="😐", key="mood_quick")
            mood_values = {"😢": -1, "😕": -0.5, "😐": 0, "🙂": 0.5, "😄": 1}
            st.session_state.health_metrics['mood_score'] = mood_values[mood_select]
            st.caption(f"Mood: {mood_select}")
        
        if st.button("💾 Save Today's Progress", use_container_width=True, type="primary"):
            st.success("✅ Progress saved for today!")
            st.balloons()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Health Score
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🎯 Your Health Score")
        
        health_score, factors = calculate_health_score()
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Circular progress indicator
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=health_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Health Score", 'font': {'size': 24}},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': PRIMARY},
                    'bgcolor': "rgba(255,255,255,0.1)",
                    'borderwidth': 2,
                    'bordercolor': "white",
                    'steps': [
                        {'range': [0, 50], 'color': 'rgba(255,107,107,0.3)'},
                        {'range': [50, 75], 'color': 'rgba(255,165,0,0.3)'},
                        {'range': [75, 100], 'color': 'rgba(78,205,196,0.3)'}
                    ],
                }
            ))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                            font={'color': "white", 'family': "Arial"}, height=250)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("**Score Breakdown:**")
            for factor in factors:
                st.write(f"• {factor}")
            
            st.write("")
            if health_score >= 75:
                st.success("🎉 Excellent! You're doing great!")
            elif health_score >= 50:
                st.info("💪 Good progress! Keep it up!")
            else:
                st.warning("🎯 Let's work on improving your health habits!")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Achievements
        badges = check_achievements()
        if badges:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("🏆 Your Achievements")
            
            cols = st.columns(min(5, len(badges)))
            for i, badge in enumerate(badges):
                with cols[i % 5]:
                    st.markdown(f"""
                    <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%); border-radius: 12px; margin: 5px; box-shadow: 0 4px 15px rgba(91,141,239,0.25);">
                        <div style="font-size: 2rem;">{badge.split()[0]}</div>
                        <div style="font-size: 0.8rem; color: white;">{' '.join(badge.split()[1:])}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

# Meal Logger Page
elif page == "Meal Logger":
    if not is_logged_in():
        st.warning("Please login first to log meals.")
    else:
        st.title("Meal Logger 🍽️")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📝 Log Your Meals")
        
        with st.form("meal_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
                meal_name = st.text_input("Meal Name", placeholder="e.g., Grilled Chicken Salad")
                meal_time = st.time_input("Time", value=datetime.now().time())
            
            with col2:
                calories = st.number_input("Calories (kcal)", min_value=0, value=0)
                protein = st.number_input("Protein (g)", min_value=0.0, value=0.0, step=0.1)
                carbs = st.number_input("Carbs (g)", min_value=0.0, value=0.0, step=0.1)
                fats = st.number_input("Fats (g)", min_value=0.0, value=0.0, step=0.1)
            
            notes = st.text_area("Notes (optional)", placeholder="How did you feel after eating?")
            
            if st.form_submit_button("🍽️ Log Meal", use_container_width=True):
                meal_entry = {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'time': meal_time.strftime("%H:%M"),
                    'type': meal_type,
                    'name': meal_name,
                    'calories': calories,
                    'protein': protein,
                    'carbs': carbs,
                    'fats': fats,
                    'notes': notes
                }
                st.session_state.meal_log.append(meal_entry)
                st.session_state.health_metrics['daily_calories'] += calories
                st.success(f"✅ {meal_type} logged: {meal_name} ({calories} kcal)")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Today's meals summary
        if st.session_state.meal_log:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📊 Today's Nutrition Summary")
            
            today = datetime.now().strftime("%Y-%m-%d")
            today_meals = [m for m in st.session_state.meal_log if m['date'] == today]
            
            if today_meals:
                total_cal = sum(m['calories'] for m in today_meals)
                total_protein = sum(m['protein'] for m in today_meals)
                total_carbs = sum(m['carbs'] for m in today_meals)
                total_fats = sum(m['fats'] for m in today_meals)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Calories", f"{total_cal} kcal")
                with col2:
                    st.metric("Protein", f"{total_protein:.1f}g")
                with col3:
                    st.metric("Carbs", f"{total_carbs:.1f}g")
                with col4:
                    st.metric("Fats", f"{total_fats:.1f}g")
                
                # Macronutrient pie chart
                fig = go.Figure(data=[go.Pie(
                    labels=['Protein', 'Carbs', 'Fats'],
                    values=[total_protein * 4, total_carbs * 4, total_fats * 9],
                    hole=.3,
                    marker_colors=[PRIMARY, ACCENT, ERROR]
                )])
                fig.update_layout(
                    title="Macronutrient Distribution (by calories)",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white')
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Meal list
                st.write("**Today's Meals:**")
                for meal in today_meals:
                    st.write(f"🍽️ **{meal['type']}** ({meal['time']}): {meal['name']} - {meal['calories']} kcal")
            else:
                st.info("No meals logged today. Start tracking your nutrition!")
            
            st.markdown('</div>', unsafe_allow_html=True)

# Progress & Goals Page
elif page == "Progress & Goals":
    if not is_logged_in():
        st.warning("Please login first to view progress.")
    else:
        st.title("Progress & Goals 🎯")
        
        # Set Goals
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⚙️ Set Your Daily Goals")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            water_goal = st.number_input("Water (glasses)", min_value=1, max_value=20, 
                                        value=st.session_state.daily_goals['water_goal'])
            st.session_state.daily_goals['water_goal'] = water_goal
        
        with col2:
            exercise_goal = st.number_input("Exercise (minutes)", min_value=10, max_value=300, 
                                           value=st.session_state.daily_goals['exercise_goal'])
            st.session_state.daily_goals['exercise_goal'] = exercise_goal
        
        with col3:
            sleep_goal = st.number_input("Sleep (hours)", min_value=4, max_value=12, 
                                        value=st.session_state.daily_goals['sleep_goal'])
            st.session_state.daily_goals['sleep_goal'] = sleep_goal
        
        with col4:
            cal_goal = st.number_input("Calories", min_value=1000, max_value=5000, 
                                      value=st.session_state.daily_goals['calories_goal'])
            st.session_state.daily_goals['calories_goal'] = cal_goal
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Weight Progress
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⚖️ Weight Progress")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("**Log Your Weight:**")
            new_weight = st.number_input("Current Weight (kg)", min_value=30.0, max_value=200.0, 
                                        value=st.session_state.user_data.get('weight', 70.0), step=0.1)
            
            if st.button("📊 Log Weight", use_container_width=True):
                weight_entry = {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'weight': new_weight
                }
                st.session_state.weight_history.append(weight_entry)
                st.session_state.user_data['weight'] = new_weight
                st.success(f"✅ Weight logged: {new_weight} kg")
        
        with col2:
            if st.session_state.weight_history:
                weight_df = pd.DataFrame(st.session_state.weight_history)
                weight_df['date'] = pd.to_datetime(weight_df['date'])
                
                fig = px.line(weight_df, x='date', y='weight',
                            title='Weight Progress Over Time',
                            labels={'weight': 'Weight (kg)', 'date': 'Date'})
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white')
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Calculate progress
                if len(st.session_state.weight_history) >= 2:
                    first_weight = st.session_state.weight_history[0]['weight']
                    latest_weight = st.session_state.weight_history[-1]['weight']
                    change = latest_weight - first_weight
                    
                    if change < 0:
                        st.success(f"🎉 You've lost {abs(change):.1f} kg!")
                    elif change > 0:
                        st.info(f"📈 You've gained {change:.1f} kg")
                    else:
                        st.info("Weight stable")
            else:
                st.info("Start logging your weight to track progress!")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Weekly Overview
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📅 Weekly Activity Overview")
        
        # Create sample weekly data
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Exercise Minutes', 'Water Intake', 'Sleep Hours', 'Mood Score')
        )
        
        # Sample data (replace with actual tracking)
        sample_exercise = [30, 45, 0, 60, 30, 90, 45]
        sample_water = [6, 8, 7, 8, 9, 6, 7]
        sample_sleep = [7, 8, 6, 7, 8, 9, 7]
        sample_mood = [0.5, 0.8, 0.3, 0.6, 0.9, 1.0, 0.7]
        
        fig.add_trace(go.Bar(x=days, y=sample_exercise, marker_color=PRIMARY, name='Exercise'), row=1, col=1)
        fig.add_trace(go.Bar(x=days, y=sample_water, marker_color=ACCENT, name='Water'), row=1, col=2)
        fig.add_trace(go.Bar(x=days, y=sample_sleep, marker_color=ERROR, name='Sleep'), row=2, col=1)
        fig.add_trace(go.Scatter(x=days, y=sample_mood, mode='lines+markers', marker_color=WARNING, name='Mood'), row=2, col=2)
        
        fig.update_layout(
            height=500,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# Health Journal Page
elif page == "Health Journal":
    if not is_logged_in():
        st.warning("Please login first to access health journal.")
    else:
        st.title("Health Journal 📔")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("✍️ Write a Journal Entry")
        
        with st.form("journal_form"):
            entry_date = st.date_input("Date", value=datetime.now())
            entry_title = st.text_input("Title", placeholder="Today's Reflection...")
            entry_content = st.text_area("Journal Entry", height=200, 
                                        placeholder="How are you feeling? What did you accomplish today? Any health insights?")
            
            col1, col2 = st.columns(2)
            with col1:
                energy_level = st.select_slider("Energy Level", 
                                               options=["Very Low", "Low", "Moderate", "High", "Very High"],
                                               value="Moderate")
            with col2:
                overall_mood = st.select_slider("Overall Mood",
                                               options=["😢 Sad", "😕 Down", "😐 Neutral", "🙂 Good", "😄 Excellent"],
                                               value="😐 Neutral")
            
            tags = st.multiselect("Tags", ["Exercise", "Nutrition", "Sleep", "Stress", "Success", "Challenge", "Gratitude"])
            
            if st.form_submit_button("💾 Save Entry", use_container_width=True):
                journal_entry = {
                    'date': entry_date.strftime("%Y-%m-%d"),
                    'title': entry_title,
                    'content': entry_content,
                    'energy_level': energy_level,
                    'mood': overall_mood,
                    'tags': tags,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.health_journal.append(journal_entry)
                st.success("✅ Journal entry saved!")
                st.balloons()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display journal entries
        if st.session_state.health_journal:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📖 Your Journal Entries")
            
            # Sort by date (newest first)
            sorted_entries = sorted(st.session_state.health_journal, 
                                  key=lambda x: x['timestamp'], reverse=True)
            
            for entry in sorted_entries:
                with st.expander(f"{entry['date']} - {entry['title'] or 'Untitled'}", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(entry['content'])
                    
                    with col2:
                        st.write(f"**Mood:** {entry['mood']}")
                        st.write(f"**Energy:** {entry['energy_level']}")
                        if entry['tags']:
                            st.write(f"**Tags:** {', '.join(entry['tags'])}")
                    
                    st.caption(f"Written on {entry['timestamp']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("📝 Start journaling to track your health journey and reflect on your progress!")

# Dashboard Page
elif page == "Dashboard":
    if not is_logged_in():
        st.warning("Please login first to view your dashboard.")
        st.info("You can login as a guest to explore the app, but full features require registration.")
    else:
        username = st.session_state.login_state.get('username', 'User')
        profile = get_user_profile(username) if not is_guest_user() else None
        
        if is_guest_user():
            st.title(f"Welcome, {username}! 👤")
            st.info("You're browsing as a guest. Register for full features and data persistence!")
        else:
            st.title(f"Welcome back, {username}! 🌟")
            if st.session_state.user_data.get('logged_in'):
                st.success("Your profile is complete! Access all features below.")
            else:
                st.warning("Complete your profile to unlock personalized recommendations!")
                if st.button("Complete Profile Now", type="primary"):
                    st.markdown("""
                    <script>
                    window.location.href = window.location.href.split('?')[0] + '?page=Profile Registration';
                    </script>
                    """, unsafe_allow_html=True)
        
        st.title("🏥 AI Wellness Guardian - Your Health Hub")
        
        if st.session_state.user_data.get('logged_in'):
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("👤 Your Profile Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Age", f"{st.session_state.user_data['age']} years")
            with col2:
                st.metric("Height", f"{st.session_state.user_data['height']} cm")
            with col3:
                st.metric("Weight", f"{st.session_state.user_data['weight']} kg")
            with col4:
                st.metric("Goal", st.session_state.user_data['mode'])
            
            st.metric("BMI", f"{st.session_state.user_data['bmi']:.1f}", st.session_state.user_data['bmi_category'])
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Health Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            bmi = st.session_state.user_data.get('bmi', 0)
            bmi_category = st.session_state.user_data.get('bmi_category', 'Normal')
            st.metric("BMI", f"{bmi:.1f}", bmi_category)
        
        with col2:
            target_calories = st.session_state.user_data.get('target_calories', 0)
            st.metric("Target Calories", f"{target_calories}", "per day")
        
        with col3:
            activity_level = st.session_state.user_data.get('physical_activity_level', 'Moderate')
            st.metric("Activity Level", activity_level)
        
        with col4:
            stress_level = st.session_state.user_data.get('stress_level', 'Moderate')
            st.metric("Stress Level", stress_level)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.mood_history or st.session_state.sleep_data:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Health Trends")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.session_state.mood_history:
                    st.write("**Mood Trend**")
                    mood_df = pd.DataFrame(st.session_state.mood_history)
                    mood_df['timestamp'] = pd.to_datetime(mood_df['timestamp'])
                    
                    fig_mood = px.line(mood_df, x='timestamp', y='polarity', 
                                     title='Mood Sentiment Over Time',
                                     labels={'polarity': 'Sentiment Score'})
                    fig_mood.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_mood, use_container_width=True)
                else:
                    st.info("No mood data available. Visit the Mood Detection page to start tracking!")
            
            with col2:
                if st.session_state.sleep_data:
                    st.write("**Sleep Trend**")
                    sleep_df = pd.DataFrame(st.session_state.sleep_data)
                    sleep_df['date'] = pd.to_datetime(sleep_df['date'])
                    
                    fig_sleep = px.line(sleep_df, x='date', y='duration', 
                                      title='Sleep Duration Over Time',
                                      labels={'duration': 'Hours'})
                    fig_sleep.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_sleep, use_container_width=True)
                else:
                    st.info("No sleep data available. Visit the Sleep Analysis page to start tracking!")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Quick Actions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🍎 Log Food", use_container_width=True):
                st.info("Visit Health Recommendations page to log food and calculate calories!")
        
        with col2:
            if st.button("💪 Log Exercise", use_container_width=True):
                st.info("Visit Health Recommendations page to track your workouts!")
        
        with col3:
            if st.button("😊 Check Mood", use_container_width=True):
                st.info("Visit Mood Detection page to analyze your current mood!")
        
        with col4:
            if st.button("💤 Log Sleep", use_container_width=True):
                st.info("Visit Sleep Analysis page to track your sleep patterns!")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("AI Health Insights")
        st.info("AI health insights will be generated by your models")
        st.markdown('</div>', unsafe_allow_html=True)

# Health Recommendations Page
elif page == "Health Recommendations":
    if not is_logged_in():
        st.warning("Please login first to access health recommendations.")
        st.info("You can login as a guest to explore the app, but full features require registration.")
    elif is_guest_user():
        st.warning("Guest users have limited access to personalized recommendations.")
        st.info("Register for full personalized health recommendations based on your profile.")
    elif not st.session_state.user_data['logged_in']:
        st.warning("Please register your profile first.")
    else:
        
        st.markdown("""
<style>

/* Page background */
body {
    background-color: #0d1117;
    color: #dbe3f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* Section Titles */
.clean-title {
    font-size: 28px;
    font-weight: 600;
    margin-top: 25px;
    color: #e2e8f0;
}

/* Big Cards */
.clean-card {
    background-color: #1c2333; 
    border-radius: 16px;
    padding: 22px;
    margin-top: 20px;
    border: 1px solid #2e3b55;
    box-shadow: 0 4px 14px rgba(0,0,0,0.4);
}

/* Mini Cards in row */
.mini-card {
    background-color: #1c2333;
    border-radius: 14px;
    padding: 18px;
    border: 1px solid #2e3b55;
    box-shadow: 0 3px 10px rgba(0,0,0,0.35);
    height: 100%;
}

/* Hover effect */
.clean-card:hover, .mini-card:hover {
    box-shadow: 0 6px 18px rgba(0,0,0,0.5);
    transition: 0.25s ease-in-out;
}

/* Subtitles */
.clean-subtitle {
    font-size: 20px;
    font-weight: 600;
    color: #aeb8d4;
    margin-bottom: 8px;
}

/* Text inside card */
.card-text {
    font-size: 17px;
    color: #dbe3f5;
    line-height: 1.6;
}

/* Buttons */
div.stButton > button {
    background-color: #2d4a7c;
    color: white;
    border-radius: 10px;
    padding: 10px 18px;
    font-size: 18px;
    border: none;
}

div.stButton > button:hover {
    background-color: #3e5ea8;
}

</style>
""", unsafe_allow_html=True)


        
        st.title("💪 Health & Wellness Recommendations")
        
        # User profile overview
        st.markdown('<div class="card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Target Calories", f"{st.session_state.user_data['target_calories']}", "per day")
        with col2:
            st.metric("BMI", f"{st.session_state.user_data['bmi']:.1f}")
        with col3:
            mode = st.session_state.user_data['mode']
            st.metric("Goal", mode.split(' ')[0])
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # =====================================================
        # LOAD USER PROFILE
        # =====================================================
        user = st.session_state.get("user_data", None)
        
        if user is None:
            st.warning("You must complete your profile first before using this page.")
            st.stop()
        
        # =====================================================
        # SMART HEALTH & FITNESS PLAN (NEW PART 1 + PART 3)
        # =====================================================

        # Enhanced Header Section
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2.5rem 2rem;
            border-radius: 20px;
            margin-bottom: 2rem;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
            text-align: center;
        ">
            <h1 style="
                color: white;
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            ">🌟 Smart Health & Fitness Plan</h1>
            <p style="
                color: rgba(255,255,255,0.95);
                font-size: 1.1rem;
                margin-top: 0.5rem;
                line-height: 1.6;
                max-width: 800px;
                margin-left: auto;
                margin-right: auto;
            ">
                Powered by advanced AI models trained on comprehensive fitness and health data to generate your complete personalized wellness plan
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Enhanced Input Section with Cards
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            padding: 1.5rem;
            border-radius: 16px;
            border: 2px solid rgba(102, 126, 234, 0.3);
            margin-bottom: 2rem;
        ">
            <h3 style="
                color: #667eea;
                font-size: 1.5rem;
                font-weight: 600;
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            ">
                🧪 Additional Health Information
            </h3>
            <p style="
                color: #dbe3f5;
                font-size: 0.95rem;
                margin-bottom: 1.5rem;
                opacity: 0.9;
            ">
                Help us personalize your plan by providing these health details
            </p>
        </div>
        """, unsafe_allow_html=True)

        colA, colB = st.columns(2)

        with colA:
            st.markdown("""
            <div style="
                background: #1c2333;
                padding: 1.2rem;
                border-radius: 12px;
                border: 1px solid #2e3b55;
                margin-bottom: 1rem;
            ">
            """, unsafe_allow_html=True)
            hypertension = st.selectbox(
                "💓 Do you have hypertension?",
                ["No", "Yes"],
                help="High blood pressure condition"
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with colB:
            st.markdown("""
            <div style="
                background: #1c2333;
                padding: 1.2rem;
                border-radius: 12px;
                border: 1px solid #2e3b55;
                margin-bottom: 1rem;
            ">
            """, unsafe_allow_html=True)
            diabetes = st.selectbox(
                "🩺 Do you have diabetes?",
                ["No", "Yes"],
                help="Diabetes condition"
            )
            st.markdown("</div>", unsafe_allow_html=True)

        hypertension_value = 1 if hypertension == "Yes" else 0
        diabetes_value = 1 if diabetes == "Yes" else 0


        # =====================================================
        # LOAD INPUT ENCODERS
        # =====================================================
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        def load_encoder(name):
            path = os.path.join(BASE_DIR, f"{name}_input_encoder.joblib")
            try:
                return joblib.load(path)
            except:
                st.error(f"Missing encoder file: {path}")
                st.stop()

        sex_enc = load_encoder("Sex")
        level_enc = load_encoder("Level")
        goal_enc = load_encoder("Fitness Goal")


        # =====================================================
        # LOAD OUTPUT MODELS + ENCODERS
        # =====================================================
        def load_output(name):
            model_path = os.path.join(BASE_DIR, f"{name}_model.joblib")
            encoder_path = os.path.join(BASE_DIR, f"{name}_output_encoder.joblib")
            try:
                model = joblib.load(model_path)
                encoder = joblib.load(encoder_path)
                return model, encoder
            except:
                st.error(f"Missing model or encoder: {name}")
                st.stop()

        targets = ["Diet", "Exercises", "Equipment", "Fitness Type", "Recommendation"]
        models = {t: load_output(t) for t in targets}


        # =====================================================
        # PREPARE INPUT VECTOR
        # =====================================================
        def safe_transform(encoder, label, encoder_name="encoder"):
            """
            Try to transform label with encoder. If label not seen, fall back safely.
            """
            try:
                return encoder.transform([label])[0]
            except Exception:
                fallback = encoder.classes_[0]
                st.warning(f"Label '{label}' not found in {encoder_name}; using '{fallback}' instead.")
                return encoder.transform([fallback])[0]


        def prepare_input_vector():
            gender = user.get("gender", "Male")
            age = user.get("age", 30)
            height = user.get("height", 170.0)
            weight = user.get("weight", 70.0)
            bmi = user.get("bmi", round(weight / ((height/100)**2), 1))

            # Determine BMI category
            bmi_cat = user.get("bmi_category")
            if not bmi_cat:
                if bmi < 18.5:
                    bmi_cat = "Underweight"
                elif bmi < 25:
                    bmi_cat = "Normal"
                elif bmi < 30:
                    bmi_cat = "Overweight"
                else:
                    bmi_cat = "Obese"

            # ---- FIX LABEL MISMATCHES ----
            bmi_map = {
                "Underweight": "Underweight",
                "Normal": "Normal",
                "Overweight": "Overweight",
                "Obese": "Obuse",      # dataset spelling
                "Obesity": "Obuse"
            }

            goal_label = user.get("mode", "Bulk Mode (Weight Gain)")

            goal_map = {
                "Bulk Mode (Weight Gain)": "Weight Gain",
                "Cut Mode (Weight Loss)": "Weight Loss",
                "Cutting Mode (Weight Loss)": "Weight Loss",
            }

            bmi_cat = bmi_map.get(bmi_cat, bmi_cat)
            goal_label = goal_map.get(goal_label, goal_label)

            # Encode inputs
            sex_encoded = safe_transform(sex_enc, gender, "Sex")
            level_encoded = safe_transform(level_enc, bmi_cat, "Level")
            goal_encoded = safe_transform(goal_enc, goal_label, "Fitness Goal")

            return np.array([[
                sex_encoded,
                age,
                height,
                weight,
                hypertension_value,
                diabetes_value,
                bmi,
                level_encoded,
                goal_encoded
            ]])


        # =====================================================
        # GENERATE PLAN BUTTON (Enhanced)
        # =====================================================
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Center the button with styling
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            generate_clicked = st.button(
                "🔮 Generate My Complete Health Plan",
                use_container_width=True,
                type="primary"
            )
        
        if generate_clicked:

            x_input = prepare_input_vector()

            results = {}

            # Predict all targets
            for target in targets:
                model, encoder = models[target]
                pred = model.predict(x_input)[0]
                decoded = encoder.inverse_transform([pred])[0]
                results[target] = decoded

            # ======================================================
            # DISPLAY RESULTS (ENHANCED GUI WITH BETTER STRUCTURE)
            # ======================================================

            # Success Message
            st.success("✅ Your personalized health plan has been generated!")
            st.markdown("<br>", unsafe_allow_html=True)

            # Enhanced Title
            st.markdown("""
            <div style="
                text-align: center;
                margin-bottom: 2.5rem;
                padding: 1.5rem;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
                border-radius: 16px;
                border: 2px solid rgba(102, 126, 234, 0.3);
            ">
                <h2 style="
                    color: #667eea;
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 0.5rem;
                ">🌟 Your Personalized Health Plan</h2>
                <p style="color: #dbe3f5; font-size: 1rem; opacity: 0.9;">
                    Tailored specifically for your health profile and goals
                </p>
            </div>
            """, unsafe_allow_html=True)

            # === Enhanced Card: General Recommendation ===
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(76, 175, 80, 0.15) 0%, rgba(56, 142, 60, 0.15) 100%);
                padding: 2rem;
                border-radius: 16px;
                border: 2px solid rgba(76, 175, 80, 0.4);
                margin-bottom: 2rem;
                box-shadow: 0 8px 24px rgba(76, 175, 80, 0.2);
            ">
                <div style="
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    margin-bottom: 1rem;
                ">
                    <span style="font-size: 2rem;">🧠</span>
                    <h3 style="
                        color: #4CAF50;
                        font-size: 1.5rem;
                        font-weight: 700;
                        margin: 0;
                    ">General Health Recommendation</h3>
                </div>
                <div style="
                    background: rgba(0, 0, 0, 0.2);
                    padding: 1.5rem;
                    border-radius: 12px;
                    border-left: 4px solid #4CAF50;
                ">
                    <p style="
                        color: #dbe3f5;
                        font-size: 1.05rem;
                        line-height: 1.8;
                        margin: 0;
                        text-align: justify;
                    ">{results['Recommendation']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # === Enhanced Card: Diet Recommendation ===
            # Better parsing: split by comma but handle items with commas inside parentheses
            diet_text = results['Diet']
            diet_items = []
            current_item = ""
            paren_count = 0
            
            for char in diet_text:
                if char == '(':
                    paren_count += 1
                    current_item += char
                elif char == ')':
                    paren_count -= 1
                    current_item += char
                elif char == ',' and paren_count == 0:
                    # Only split on comma if not inside parentheses
                    if current_item.strip():
                        diet_items.append(current_item.strip())
                    current_item = ""
                else:
                    current_item += char
            
            # Add the last item
            if current_item.strip():
                diet_items.append(current_item.strip())
            
            # If parsing failed, fall back to simple split
            if not diet_items:
                diet_items = [item.strip() for item in results['Diet'].split(",") if item.strip()]
            
            diet_html_items = "".join([
                '<div style="'
                'background: rgba(255, 204, 0, 0.1);'
                'padding: 0.75rem 1rem;'
                'margin: 0.5rem 0;'
                'border-radius: 8px;'
                'border-left: 3px solid #ffcc00;'
                'display: flex;'
                'align-items: flex-start;'
                'gap: 0.75rem;'
                'word-wrap: break-word;'
                'overflow-wrap: break-word;'
                '">'
                '<span style="color: #ffcc00; font-size: 1.2rem; flex-shrink: 0; margin-top: 0.1rem;">✓</span>'
                '<span style="'
                'color: #dbe3f5;'
                'font-size: 1rem;'
                'line-height: 1.7;'
                'word-wrap: break-word;'
                'overflow-wrap: break-word;'
                'flex: 1;'
                '">' + html.escape(item) + '</span>'
                '</div>'
                for item in diet_items if item
            ])

            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(255, 204, 0, 0.15) 0%, rgba(255, 193, 7, 0.15) 100%);
                padding: 2rem;
                border-radius: 16px;
                border: 2px solid rgba(255, 204, 0, 0.4);
                margin-bottom: 2rem;
                box-shadow: 0 8px 24px rgba(255, 204, 0, 0.2);
            ">
                <div style="
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    margin-bottom: 1.5rem;
                ">
                    <span style="font-size: 2rem;">🥗</span>
                    <h3 style="
                        color: #ffcc00;
                        font-size: 1.5rem;
                        font-weight: 700;
                        margin: 0;
                    ">Diet Recommendation</h3>
                </div>
                <div style="
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                ">
                    {diet_html_items}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # === Enhanced Row of 3 Cards with better structure ===
            st.markdown("""
            <div style="margin-top: 2rem; margin-bottom: 1rem;">
                <h3 style="
                    color: #dbe3f5;
                    font-size: 1.3rem;
                    font-weight: 600;
                    margin-bottom: 1.5rem;
                    text-align: center;
                ">📋 Your Fitness Plan Details</h3>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)

            # Fitness Type - Enhanced Card
            with col1:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, rgba(0, 191, 255, 0.15) 0%, rgba(0, 150, 255, 0.15) 100%);
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 2px solid rgba(0, 191, 255, 0.4);
                    height: 100%;
                    box-shadow: 0 6px 20px rgba(0, 191, 255, 0.2);
                    display: flex;
                    flex-direction: column;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 0.5rem;
                        margin-bottom: 1rem;
                    ">
                        <span style="font-size: 1.8rem;">🎯</span>
                        <h4 style="
                            color: #00bfff;
                            font-size: 1.2rem;
                            font-weight: 700;
                            margin: 0;
                        ">Fitness Type</h4>
                    </div>
                    <div style="
                        background: rgba(0, 0, 0, 0.2);
                        padding: 1rem;
                        border-radius: 10px;
                        flex-grow: 1;
                        display: flex;
                        align-items: center;
                    ">
                        <p style="
                            color: #dbe3f5;
                            font-size: 1rem;
                            line-height: 1.6;
                            margin: 0;
                            font-weight: 500;
                        ">{results['Fitness Type']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Exercises - Enhanced Card
            with col2:
                # Better parsing for exercises
                exercises_text = results['Exercises']
                exercises_items = []
                current_item = ""
                paren_count = 0
                
                for char in exercises_text:
                    if char == '(':
                        paren_count += 1
                        current_item += char
                    elif char == ')':
                        paren_count -= 1
                        current_item += char
                    elif char == ',' and paren_count == 0:
                        if current_item.strip():
                            exercises_items.append(current_item.strip())
                        current_item = ""
                    else:
                        current_item += char
                
                if current_item.strip():
                    exercises_items.append(current_item.strip())
                
                if not exercises_items:
                    exercises_items = [item.strip() for item in results['Exercises'].split(",") if item.strip()]
                
                exercises_html = "".join([
                    '<div style="'
                    'background: rgba(255, 87, 51, 0.1);'
                    'padding: 0.6rem 0.8rem;'
                    'margin: 0.4rem 0;'
                    'border-radius: 8px;'
                    'border-left: 3px solid #ff5733;'
                    'display: flex;'
                    'align-items: flex-start;'
                    'gap: 0.5rem;'
                    'word-wrap: break-word;'
                    'overflow-wrap: break-word;'
                    '">'
                    '<span style="color: #ff5733; flex-shrink: 0; margin-top: 0.2rem;">•</span>'
                    '<span style="'
                    'color: #dbe3f5;'
                    'font-size: 0.95rem;'
                    'line-height: 1.6;'
                    'word-wrap: break-word;'
                    'overflow-wrap: break-word;'
                    'flex: 1;'
                    '">' + html.escape(item) + '</span>'
                    '</div>'
                    for item in exercises_items if item
                ])

                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, rgba(255, 87, 51, 0.15) 0%, rgba(255, 69, 0, 0.15) 100%);
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 2px solid rgba(255, 87, 51, 0.4);
                    height: 100%;
                    box-shadow: 0 6px 20px rgba(255, 87, 51, 0.2);
                    display: flex;
                    flex-direction: column;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 0.5rem;
                        margin-bottom: 1rem;
                    ">
                        <span style="font-size: 1.8rem;">🏋️</span>
                        <h4 style="
                            color: #ff5733;
                            font-size: 1.2rem;
                            font-weight: 700;
                            margin: 0;
                        ">Exercises</h4>
                    </div>
                    <div style="
                        display: flex;
                        flex-direction: column;
                        gap: 0.4rem;
                        flex-grow: 1;
                    ">
                        {exercises_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Equipment - Enhanced Card
            with col3:
                # Better parsing for equipment
                equipment_text = results['Equipment']
                equipment_items = []
                current_item = ""
                paren_count = 0
                
                for char in equipment_text:
                    if char == '(':
                        paren_count += 1
                        current_item += char
                    elif char == ')':
                        paren_count -= 1
                        current_item += char
                    elif char == ',' and paren_count == 0:
                        if current_item.strip():
                            equipment_items.append(current_item.strip())
                        current_item = ""
                    else:
                        current_item += char
                
                if current_item.strip():
                    equipment_items.append(current_item.strip())
                
                if not equipment_items:
                    equipment_items = [item.strip() for item in results['Equipment'].split(",") if item.strip()]
                
                equipment_html = "".join([
                    '<div style="'
                    'background: rgba(199, 0, 57, 0.1);'
                    'padding: 0.6rem 0.8rem;'
                    'margin: 0.4rem 0;'
                    'border-radius: 8px;'
                    'border-left: 3px solid #c70039;'
                    'display: flex;'
                    'align-items: flex-start;'
                    'gap: 0.5rem;'
                    'word-wrap: break-word;'
                    'overflow-wrap: break-word;'
                    '">'
                    '<span style="color: #c70039; flex-shrink: 0; margin-top: 0.2rem;">⚙️</span>'
                    '<span style="'
                    'color: #dbe3f5;'
                    'font-size: 0.95rem;'
                    'line-height: 1.6;'
                    'word-wrap: break-word;'
                    'overflow-wrap: break-word;'
                    'flex: 1;'
                    '">' + html.escape(item) + '</span>'
                    '</div>'
                    for item in equipment_items if item
                ])

                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, rgba(199, 0, 57, 0.15) 0%, rgba(180, 0, 50, 0.15) 100%);
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 2px solid rgba(199, 0, 57, 0.4);
                    height: 100%;
                    box-shadow: 0 6px 20px rgba(199, 0, 57, 0.2);
                    display: flex;
                    flex-direction: column;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 0.5rem;
                        margin-bottom: 1rem;
                    ">
                        <span style="font-size: 1.8rem;">🛠️</span>
                        <h4 style="
                            color: #c70039;
                            font-size: 1.2rem;
                            font-weight: 700;
                            margin: 0;
                        ">Required Equipment</h4>
                    </div>
                    <div style="
                        display: flex;
                        flex-direction: column;
                        gap: 0.4rem;
                        flex-grow: 1;
                    ">
                        {equipment_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Footer note
            st.markdown("""
            <div style="
                margin-top: 2.5rem;
                padding: 1.5rem;
                background: rgba(102, 126, 234, 0.1);
                border-radius: 12px;
                border: 1px solid rgba(102, 126, 234, 0.3);
                text-align: center;
            ">
                <p style="
                    color: #dbe3f5;
                    font-size: 0.95rem;
                    margin: 0;
                    opacity: 0.9;
                ">
                    💡 <strong>Tip:</strong> Follow this plan consistently and track your progress for best results. 
                    Remember to consult with healthcare professionals for medical concerns.
                </p>
            </div>
            """, unsafe_allow_html=True)
        # ====== Paths (update to your real locations if needed) ======
        # Define the same feature engineering function
        def add_features(X):
            X = X.copy()
            X["Total_Calories"] = X["Protein(g)"]*4 + X["Carbs(g)"]*4 + X["Fat(g)"]*9
            X["Protein_Ratio"] = X["Protein(g)"] / X["Total_Calories"]
            X["Carb_Ratio"] = X["Carbs(g)"] / X["Total_Calories"]
            X["Fat_Ratio"] = X["Fat(g)"] / X["Total_Calories"]
            X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
            return X
        DATA_CSV = os.path.join(BASE_DIR, "All_Diets.csv")
        PIPELINE_FILE = os.path.join(BASE_DIR, "food_pipeline.joblib")
        ENCODER_FILE = os.path.join(BASE_DIR, "diet_label_encoder.joblib")

        # ====== Load ML pipeline & encoder ======
        pipeline = joblib.load(PIPELINE_FILE)
        diet_encoder = joblib.load(ENCODER_FILE)

        # ============================================================
        # 🔹 Load food dataset safely + calculate Calories
        def load_food_df():
            df = pd.read_csv(DATA_CSV)
            for c in ["Protein(g)", "Carbs(g)", "Fat(g)"]:
                if c not in df.columns:
                    df[c] = 0
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            # ✅ Calculate Calories if missing or outdated
            df["Calories"] = (df["Protein(g)"] * 4) + (df["Carbs(g)"] * 4) + (df["Fat(g)"] * 9)
            return df

        # ============================================================
        # 🔹 Append new meal row safely
        def append_new_meal_to_csv(row_dict):
            new_row_df = pd.DataFrame([row_dict])
            header = not os.path.exists(DATA_CSV)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            try:
                new_row_df.to_csv(tmp.name, index=False, header=header, mode="w")
                tmp.close()
                if header:
                    os.replace(tmp.name, DATA_CSV)
                else:
                    with open(DATA_CSV, "a", encoding="utf-8", newline="") as f:
                        new_row_df.to_csv(f, index=False, header=False)
                    os.remove(tmp.name)
            except Exception as e:
                try: os.remove(tmp.name)
                except: pass
                raise e

        # ============================================================
        # 🔹 Hybrid recommender
        def generate_hybrid_recommendations(user_data, selected_diets, food_df, pipeline, encoder):
            df = food_df.copy()

            # Fill missing Diet_type using ML predictions
            mask_missing = df["Diet_type"].isnull() | (df["Diet_type"].astype(str).str.strip() == "")
            if mask_missing.any():
                X = df.loc[mask_missing, ["Protein(g)", "Carbs(g)", "Fat(g)"]]
                if not X.empty:
                    preds = pipeline.predict(X)
                    df.loc[mask_missing, "Predicted_Diet"] = encoder.inverse_transform(preds)
            df.loc[~mask_missing, "Predicted_Diet"] = df.loc[~mask_missing, "Diet_type"].astype(str).str.lower()

            # Apply filters
            if selected_diets:
                df = df[df["Predicted_Diet"].isin(selected_diets)].copy()

            # Score meals based on goal
            goal = user_data.get("mode", "maintenance").lower()
            if "bulk" in goal:
                df["Score"] = df["Protein(g)"]*2 - df["Fat(g)"]
            elif "cut" in goal:
                df["Score"] = -df["Fat(g)"] + df["Protein(g)"]
            else:
                df["Score"] = -(abs(df["Protein(g)"] - df["Carbs(g)"]))

            df = df.sort_values(by="Score", ascending=False)

            # Pick 6 diverse top meals
            n = 6
            top = df.head(n*2)
            recs = top.sample(n=min(n, len(top)), random_state=None) if not top.empty else pd.DataFrame()
            recs = recs.sort_values(by="Score", ascending=False)
            return recs[["Recipe_name", "Cuisine_type", "Diet_type", "Predicted_Diet",
                        "Protein(g)", "Carbs(g)", "Fat(g)", "Calories"]]

        # ============================================================
        # 🔹 Display recommendations as cards
        def display_recommendation_cards(recs):
            if recs is None or recs.empty:
                st.warning("No recommendations found. Try loosening filters.")
                return

            # --- CSS (scoped only to recommendation cards) ---
            st.markdown("""
    <style>
    /* Card layout and style */
    .rec-card {
        background: rgba(255,255,255,0.05);
        border-radius: 20px;
        padding: 22px;
        margin: 10px; /* 🔹 Add equal spacing between cards */
        box-shadow: 0 3px 12px rgba(0,0,0,0.25);
        transition: transform 0.25s ease-in-out, box-shadow 0.25s ease-in-out, background 0.25s ease-in-out;
        min-height: 270px;
        font-family: 'Segoe UI', Roboto, Arial, sans-serif;
    }
    .rec-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 6px 18px rgba(0,0,0,0.4);
        background: rgba(255,255,255,0.08);
    }
    .rec-card-title {
        color: #fff;
        font-size: 1.25rem;
        font-weight: 650;
        margin-bottom: 4px;
    }
    .rec-card-sub {
        color: #A0A3B1;
        font-size: 1rem;
        margin-bottom: 12px;
    }
    .rec-card hr {
        border: 0;
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 10px 0;
    }
    .rec-nutrition {
        font-size: 1rem;
        color: #E6E6F0;
        line-height: 1.5;
        font-weight: 500;
    }
    .rec-calories {
        color: #FFD966;
        font-weight: 700;
        font-size: 1.1rem;
        text-align: right;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

            # --- Card Grid ---
            num_cols = 3
            for i in range(0, len(recs), num_cols):
                cols = st.columns(num_cols, gap="large")
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(recs):
                        break

                    row = recs.iloc[idx]
                    safe_name = html.escape(str(row["Recipe_name"]))
                    safe_cuisine = html.escape(str(row.get("Cuisine_type", "")))
                    diet_true = str(row.get("Diet_type", ""))

                    protein = int(round(row["Protein(g)"]))
                    carbs = int(round(row["Carbs(g)"]))
                    fat = int(round(row["Fat(g)"]))
                    calories = int(round(row["Calories"]))

                    html_card = f"""
            <div class="rec-card">
                <div>
                    <div class="rec-card-title">🍽️ {safe_name}</div>
                    <div class="rec-card-sub">🌍 {safe_cuisine}</div>
                    <div class="rec-card-sub">🥗 Diet: <b>{diet_true}</b></div>
                    <hr/>
                    <div class="rec-nutrition">
                        💪 Protein: <b>{protein}</b> g<br/>
                        🍞 Carbs: <b>{carbs}</b> g<br/>
                        🧈 Fat: <b>{fat}</b> g
                    </div>
                </div>
                <div class="rec-calories">🔥 {calories} kcal</div>
            </div>
            """

                    with col:
                        # Center the card visually and add a bit of top/bottom gap
                        st.markdown(f"<div style='display:flex; justify-content:center; margin-bottom:20px;'>{html_card}</div>", unsafe_allow_html=True)

        # ============================================================
        # 🔹 Add new meal form (AI classification + save)
        def add_meal_form():
            st.subheader("➕ Add / Classify a New Meal")
            st.write("Enter meal info, let the AI classify it, then optionally save it to the dataset.")

            with st.form("add_meal", clear_on_submit=False):
                name = st.text_input("Recipe name")
                cuisine = st.text_input("Cuisine type (optional)")
                protein = st.number_input("Protein (g)", min_value=0.0, value=20.0, step=1.0, format="%.2f")
                carbs = st.number_input("Carbs (g)", min_value=0.0, value=30.0, step=1.0, format="%.2f")
                fat = st.number_input("Fat (g)", min_value=0.0, value=10.0, step=1.0, format="%.2f")
                user_override = st.selectbox("If you already know the diet, choose it (optional)",
                                     ["", "paleo", "vegan", "keto", "mediterranean", "dash"])
                submit = st.form_submit_button("Classify Meal")

            if submit:
                if not name.strip():
                    st.error("Please provide a recipe name.")
                    return None

                # Predict diet with ML
                X_new = pd.DataFrame([{"Protein(g)": protein, "Carbs(g)": carbs, "Fat(g)": fat}])
                pred_encoded = pipeline.predict(X_new)[0]
                pred_label = diet_encoder.inverse_transform([pred_encoded])[0]

                calories = (float(protein) * 4) + (float(carbs) * 4) + (float(fat) * 9)

                st.markdown("**AI classification result:**")
                st.info(f"Predicted diet: **{pred_label.upper()}**")

                if user_override:
                    st.caption(f"User override set: **{user_override}** — will use this instead of AI label when saving.")

                # Show preview
                st.markdown("**Preview:**")
                safe_name = html.escape(name)
                st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.04); padding:12px; border-radius:10px;">
                    <h4 style="margin:4px 0;">🍽️ {safe_name}</h4>
                    <p style="margin:0;">🌍 Cuisine: {html.escape(cuisine or '-')}</p>
                    <p style="margin:0;">🥗 Predicted Diet: <b>{pred_label}</b></p>
                    <p style="margin:0;">💪 Protein: {protein}g • 🍞 Carbs: {carbs}g • 🧈 Fat: {fat}g • 🔥 Calories: {int(calories)} kcal</p>
                    </div>
                """, unsafe_allow_html=True)

                if st.button("💾 Save this meal (AI label)"):
                    row = {
                        "Recipe_name": name.strip(),
                        "Diet_type": pred_label,
                        "Cuisine_type": cuisine.strip() if cuisine else "",
                        "Protein(g)": float(protein),
                        "Carbs(g)": float(carbs),
                        "Fat(g)": float(fat),
                        "Calories": calories,
                        "Extraction_day": datetime.utcnow().date().isoformat(),
                        "Extraction_time": datetime.utcnow().time().isoformat()
                    }
                    append_new_meal_to_csv(row)
                    st.success("✅ Saved with AI label.")
                    return row

                if user_override and st.button("💾 Save this meal (Manual label)"):
                    row = {
                        "Recipe_name": name.strip(),
                        "Diet_type": user_override,
                        "Cuisine_type": cuisine.strip() if cuisine else "",
                        "Protein(g)": float(protein),
                        "Carbs(g)": float(carbs),
                        "Fat(g)": float(fat),
                        "Calories": calories,
                        "Extraction_day": datetime.utcnow().date().isoformat(),
                        "Extraction_time": datetime.utcnow().time().isoformat()
                    }
                    append_new_meal_to_csv(row)
                    st.success("✅ Saved with manual label.")
                    return row
            return None


        # ============================================================
        # 🔹 Main health recommendations page
        def health_recommendations_page():
            st.title("🥗 Eat Smarter, 🔥 Train Better")

            food_df = load_food_df()

            # --- Checkbox UI with descriptions & recommended diets ---
            st.write("Choose your diet preferences:")
            cols = st.columns(3)
            chosen_diets = []

            diet_info = {
                "paleo": "Focuses on whole foods, lean meats, fruits, and vegetables. ❌ Avoids grains and processed foods.",
                "vegan": "Plant-based diet that eliminates all animal products. ✅ Good for cholesterol, ❌ may lack protein.",
                "keto": "Low-carb, high-fat diet. ✅ Great for fat loss, ❌ can be hard to sustain long-term.",
                "mediterranean": "Balanced diet rich in olive oil, fish, fruits, and grains. ❤️ Good for heart health.",
                "dash": "Designed to reduce blood pressure. ✅ Heart-friendly, ❌ may be moderate in protein."
            }

            recommended_diets = []
            goal = st.session_state.user_data.get("mode", "maintenance") if "user_data" in st.session_state else "maintenance"
            goal = goal.lower()

            if "bulk" in goal:
                recommended_diets = ["paleo", "mediterranean"]
            elif "cut" in goal:
                recommended_diets = ["keto", "dash"]
            else:
                recommended_diets = ["mediterranean", "dash"]

            for i, (diet, desc) in enumerate(diet_info.items()):
                with cols[i % 3]:
                    is_recommended = diet in recommended_diets
                    label = f"{diet.title()} Diet"
                    if is_recommended:
                        label += " ⭐ (Recommended)"
                    checked = st.checkbox(label, value=is_recommended)
                    if checked:
                        chosen_diets.append(diet)
                    st.caption(desc)

            # --- Generate Recommendations ---
            if st.button("🤖 Generate Food Recommendations"):
                recs = generate_hybrid_recommendations({"mode": goal}, chosen_diets, food_df, pipeline, diet_encoder)
                display_recommendation_cards(recs)
                
            # --- Add meal form ---
            add_meal_form()
        
        # Call the health recommendations page function
        health_recommendations_page()

        st.markdown('</div>', unsafe_allow_html=True)


# Mood Detection Page
# Mood Detection Page (improved: uses form, reloads model if missing, shows fresh recommendations)
elif page == "Mood Detection":
    st.title("Mood Detection 😊")
    # Added separator for professional look
    st.markdown("---")

    if not is_logged_in():
        st.warning("Please login first to view your dashboard.")
        st.info("You can login as a guest to explore the app, but full features require registration.")
    
    else:
        # Lazy load mood model when needed
        if mood_model is None and TRANSFORMERS_AVAILABLE:
            with st.spinner("Loading mood detection model..."):
                mood_model = load_mood_model()

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("How are you feeling today?")

        with st.form("mood_form"):
            mood_input = st.text_area(
                "Describe your current mood, thoughts, or feelings:",
                placeholder="I'm feeling...",
                height=120,
                key="mood_input"
            )
            analyze_submit = st.form_submit_button("Analyze Mood", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")

        if analyze_submit:
            if not mood_input or not mood_input.strip():
                st.error("Please describe how you're feeling.")
            else:
                # Ensure model is loaded
                if mood_model is None:
                    if TRANSFORMERS_AVAILABLE:
                        with st.spinner("Loading mood detection model..."):
                            mood_model = load_mood_model()
                    else:
                        st.error("⚠️ Mood detection is not available. Please install transformers library: `pip install transformers torch`")
                        st.stop()

                if mood_model is not None:
                    try:
                        with st.spinner("Analyzing your mood..."):
                            preds = mood_model(mood_input)[0]  # قائمة المشاعر واحتمالاتها
                            preds_sorted = sorted(preds, key=lambda x: x["score"], reverse=True)

                        # عرض المشاعر كلها مع الاحتمالات
                        
                        st.subheader("🎭 Top 3 Detected Emotions:")
                        top_3 = preds_sorted[:3]

                        for p in top_3:
                            emoji = EMOJI_DICT.get(p["label"].lower(), "🙂")
                            st.markdown(f"**{emoji} {p['label']}** — {p['score']:.2f}")
                            st.progress(p["score"])
                        
                        dominant = preds_sorted[0]
                        mood_label = dominant["label"]
                        polarity = dominant["score"]
                        emoji = EMOJI_DICT.get(mood_label.lower(), "🙂")

                        # تخزين في الحالة
                        mood_entry = {
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            'text': mood_input,
                            'mood': mood_label,
                            'polarity': polarity,
                            'emoji': emoji
                        }
                        st.session_state.mood_history.append(mood_entry)
                        st.session_state.health_metrics['mood_score'] = polarity

                        # عرض الميتريكس
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Dominant Mood", f"{emoji} {mood_label}")
                        with col2:
                            st.metric("Top Emotion Score", f"{polarity:.2f}")
                        with col3:
                            st.metric("Analysis Time", datetime.now().strftime("%H:%M"))
                        # Personalized Mood-Based Recommendations Section
                        st.subheader("💡 Personalized Recommendations Just for You")

                        EMOJI_DICT = {
                    "admiration": "✨", "amusement": "😄", "anger": "😡", "annoyance": "😤",
                    "approval": "👍", "caring": "🤗", "confusion": "🤔", "curiosity": "🧐",
                    "desire": "🔥", "disappointment": "😞", "disapproval": "👎", "disgust": "🤢",
                    "embarrassment": "😳", "excitement": "🤩", "fear": "😨", "gratitude": "🙏",
                    "grief": "💔", "joy": "😊", "love": "❤️", "neutral": "😐", "nervousness": "😬",
                    "optimism": "🙂", "pride": "🏅", "realization": "💡", "relief": "😌",
                    "remorse": "😔", "sadness": "😢", "surprise": "😲"
                }

                        advice_pool = {
                    "sadness": [
                        "🤍 Allow yourself to feel — try a gentle self-care activity (warm bath, favorite song).",
                        "🗣️ Share how you feel with someone trusted, even briefly — connection helps.",
                        "📝 Write one small thing you're grateful for today to shift perspective.",
                        "🚶 Take a short walk outside to change scenery and lift your mood."
                    ],
                    "anxiety": [
                        "🧘‍♀️ Practice 5 minutes of focused breathing (inhale 4 — hold 4 — exhale 4).",
                        "📋 Break tasks into tiny steps and complete one small item to reduce overwhelm.",
                        "✍️ Journal your worries for 5 minutes to get them out of your head.",
                        "🔁 Use grounding techniques (name 5 things you see, 4 you can touch) to return to the present."
                    ],
                    "joy": [
                        "🎉 Celebrate the moment — share your good news or reward yourself kindly.",
                        "📣 Spread the positivity: tell someone what made you happy today.",
                        "🎨 Do a short creative activity that amplifies your joy (draw, sing, dance).",
                        "🤝 Connect with someone who lifts you up to prolong the positive feeling."
                    ],
                    "anger": [
                        "🛑 Pause and breathe for 30 seconds before reacting to defuse intensity.",
                        "🏃‍♂️ Channel energy into movement (brisk walk, push-ups) to release tension.",
                        "🗂️ Name the problem and one practical next step — focus on solutions, not blame.",
                        "🗣️ If safe, express your feelings calmly using “I” statements (I feel… because…)."
                    ],
                    "fear": [
                        "🦶 Ground yourself: take slow breaths and focus on one small next action.",
                        "📐 Break the feared situation into manageable parts and address the first step.",
                        "🤝 Talk through the fear with someone you trust to gain perspective.",
                        "🔎 Check facts vs. assumptions — identify any evidence that reduces the fear."
                    ],
                    "neutral": [
                        "📅 Plan a small meaningful goal for today to add purpose and momentum.",
                        "☕ Take a mindful break — notice sensations in a short pause to reset focus.",
                        "⚖️ Keep a balanced routine: light movement, nutritious meal, and short rest.",
                        "🔄 Reflect briefly on one positive and one constructive thing to guide your day."
                    ]
                }

                        def generate_rule_based_advice(emotions, max_advices=3):
                            advices = []
                            sorted_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)

                            for emo, score in sorted_emotions:
                                if emo in advice_pool:
                                    max_possible = len(advice_pool[emo])
                                    count = max(1, min(max_possible, int(score * max_possible * 2)))
                                    selected = advice_pool[emo][:min(count, max_possible)]
                                    
                                    advices.extend(selected)

                            return advices[:max_advices]

                        def detect_emotions(text):
                            emotions_dict = {}
                            keywords = {
                                'sad': 'sadness',
                                'happy': 'joy',
                                'excited': 'joy',
                                'anxious': 'anxiety',
                                'stressed': 'anxiety',
                                'angry': 'anger',
                                'fear': 'fear'
                            }
                            
                            text_lower = text.lower()
                            for word, emo in keywords.items():
                                if word in text_lower:
                                    emotions_dict[emo] = emotions_dict.get(emo, 0) + 0.6
                            if not emotions_dict:
                                emotions_dict['neutral'] = 0.5
                            return emotions_dict

                        emotions_dict = {p['label'].lower(): p['score'] for p in preds_sorted}

                        advice_list = generate_rule_based_advice(emotions_dict)
                        for advice in advice_list:
                            st.write(advice)
                        
                    except Exception as e:
                        st.error(f"An error occurred during mood analysis: {str(e)}")
                        st.info("Please try again. If the problem persists, the model may need to be downloaded.")
                else:
                    st.error("⚠️ Mood detection is not available. Please install transformers library: `pip install transformers torch`")


    # Mood history and trends
    if is_logged_in() and st.session_state.mood_history:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Mood History & Trends")
        st.markdown("---")


        # Create mood history DataFrame safely
        try:
            # Requires pandas (pd) and plotly.express (px)
            mood_df = pd.DataFrame(st.session_state.mood_history)
            mood_df['timestamp'] = pd.to_datetime(mood_df['timestamp'])
            # Plot mood trends
            fig = px.line(
                mood_df.sort_values('timestamp'),
                x='timestamp', y='polarity',
                title='Mood Sentiment Over Time',
                labels={'polarity': 'Sentiment (0-1)', 'timestamp': 'Time'}
            )
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("Unable to render mood trend chart right now.")

        # Recent mood entries (most recent first)
        st.write("**Recent Mood Entries:**")
        for entry in reversed(st.session_state.mood_history[-8:]):
            ts = entry.get('timestamp', '')
            emoji = entry.get('emoji', '')
            text = entry.get('text', '')[:120]
            st.write(f"{emoji} {ts}: {text}")

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")

    # Activity suggestions card (static suggestions for now)
    if is_logged_in():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🎯 Mood-Boosting Activities")
        st.markdown("---")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**Physical Activities**")
            activities = ["Yoga 🧘 (10-20 min)", "Walk 🚶 (15-30 min)", "Dance 💃 (10 min)", "Stretching 🧎 (5-10 min)"]
            for activity in activities:
                st.write(f"• {activity}")

        with col2:
            st.write("**Mental Activities**")
            activities = ["Breathing exercise (4-4-4)", "Journaling ✍️ (5 min)", "Read a short uplifting article 📚", "Guided meditation 🎧"]
            for activity in activities:
                st.write(f"• {activity}")

        with col3:
            st.write("**Social Activities**")
            activities = ["Call a friend 📞 (5 min)", "Send a message to someone you trust 💬", "Join a local group/event 👥", "Volunteer / help someone 🤝"]
            for activity in activities:
                st.write(f"• {activity}")

        st.markdown('</div>', unsafe_allow_html=True)
   

elif page == "Sleep Analysis":
    st.title("Sleep Analysis 💤")
    if not is_logged_in():
        st.warning("Please login first to view your dashboard.")
        st.info("You can login as a guest to explore the app, but full features require registration.")
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📝 Log Your Sleep Data")
        st.write("Track your sleep patterns to receive AI-powered insights and personalized recommendations.")

        # Color constants (already defined at top, but keeping local for compatibility)
        SUCCESS = 'green'
        ERROR = 'red'
        WARNING = 'orange'
        ACCENT = 'blue'

        with st.form("sleep_tracking"):
            st.markdown("**⏰ Sleep Schedule**")
            bedtime = st.time_input(
            "Bedtime",
            value=datetime.strptime("22:00", "%H:%M").time(),
            key="bedtime_input"
            )
            wake_time = st.time_input(
            "Wake Time",
            value=datetime.strptime("07:00", "%H:%M").time(),
            key="wake_time_input"
            )


            sleep_latency = st.number_input(
                "Time to Fall Asleep (minutes)",
                min_value=0,
                max_value=120,
                value=15,
                key="sleep_latency"
            )
            awakenings = st.number_input(
                "Number of Awakenings",
                min_value=0,
                max_value=10,
                value=0,
                key="awakenings_input"
            )

            st.markdown("**😴 Sleep Quality Assessment**")
            col_q1, col_q2, col_q3 = st.columns(3)

            with col_q1:
                sleep_quality = st.select_slider(
                    "Sleep Quality Rating",
                    options=["Poor", "Fair", "Good", "Excellent"],
                    value="Good",
                    key="sleep_quality_slider"
                )

            with col_q2:
                activity_level = st.select_slider(
                    "Physical Activity Level",
                    options=["Low", "Moderate", "High"],
                    value="Moderate",
                    key="activity_level_slider"
                )

            with col_q3:
                stress_level = st.select_slider(
                    "Stress Level",
                    options=["Low", "Moderate", "High"],
                    value="Moderate",
                    key="stress_level_slider"
                )

            st.markdown("**📝 Additional Notes**")
            sleep_notes = st.text_area("Sleep observations (optional)",
                                        placeholder="Any observations about your sleep quality, dreams, or factors affecting sleep...",
                                        height=80, key="sleep_notes_area")

            col_submit, col_info = st.columns([2, 1])

            with col_submit:
                submit_btn = st.form_submit_button("💾 Save Sleep Record", use_container_width=True, type="primary")

            with col_info:
                st.info("✅ Data saves securely to your profile", icon="ℹ️")

        if submit_btn:
            # Calculate sleep duration
            bedtime_dt = datetime.combine(datetime.today(), bedtime)
            wake_dt = datetime.combine(datetime.today(), wake_time)
            if wake_dt <= bedtime_dt:
                wake_dt += timedelta(days=1)

            sleep_duration = (wake_dt - bedtime_dt).total_seconds() / 3600.0

            # Prevent division by zero and clamp values
            sleep_efficiency = 0.0
            try:
                if sleep_duration > 0:
                    sleep_efficiency = max(
                        0.0,
                        (sleep_duration - (sleep_latency / 60.0) - (awakenings * 0.25))
                        / sleep_duration
                        * 100.0,
                    )
            except Exception:
                sleep_efficiency = 0.0

            # Build sleep entry
            sleep_entry = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "bedtime": bedtime.strftime("%H:%M"),
                "wake_time": wake_time.strftime("%H:%M"),
                "duration": round(sleep_duration, 2),
                "quality": sleep_quality,
                "latency": int(sleep_latency),
                "awakenings": int(awakenings),
                "efficiency": round(sleep_efficiency, 1),
                "activity_level": activity_level,
                "stress_level": stress_level,
                "notes": sleep_notes,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Ensure session storage exists and append
            if "sleep_data" not in st.session_state or not isinstance(st.session_state.sleep_data, list):
                st.session_state.sleep_data = []
            st.session_state.sleep_data.append(sleep_entry)

            # Update aggregated metrics
            st.session_state.health_metrics["sleep_hours"] = sleep_duration

            # Load AI sleep-disorder assessment model
            try:
                model = load_sleep_disorder_model()
            except NameError:
                model = None

            if model is not None:

                if model is not None:
                    try:
                        # Defensive mapping with defaults
                        quality_map = {"Poor": 1, "Fair": 2, "Good": 3, "Excellent": 4}
                        activity_map = {"Low": 1, "Moderate": 2, "High": 3}
                        stress_map = {"Low": 1, "Moderate": 2, "High": 3}

                        X_pred = pd.DataFrame([{
                            'Person ID': 0,
                            'Gender': 1,
                            'Age': 25,
                            'Occupation': 0,
                            'Sleep Duration': sleep_duration,
                            'Quality of Sleep': quality_map[sleep_quality],
                            'Physical Activity Level': activity_map[activity_level],
                            'Stress Level': stress_map[stress_level],
                            'BMI Category': 0,
                            'Blood Pressure': 120,
                            'Heart Rate': 70,
                            'Daily Steps': 5000
                        }])
                        # Model prediction with error handling
                        try:
                            pred = model.predict(X_pred)[0]
                        except Exception:
                            pred = model.predict(X_pred.values)[0]

                        sleep_disorder_label = "😴 Healthy Sleep Pattern" if int(pred) == 0 else "⚠️ Possible Sleep Concern"

                        # Get confidence score if available
                        confidence_str = ""
                        try:
                            if hasattr(model, "predict_proba"):
                                proba = model.predict_proba(X_pred)
                                prob_max = float(proba[0].max())
                                confidence_str = f" ({prob_max*100:.0f}%)"
                            else:
                                # Ensure we don't try to access proba if model doesn't support it
                                pass
                        except Exception:
                            pass

                        st.success("✅ Sleep record saved successfully!")
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Sleep Duration", f"{sleep_duration:.1f} hrs")
                        with col_b:
                            st.metric("Sleep Efficiency", f"{sleep_efficiency:.1f}%")
                        with col_c:
                            st.metric("AI Assessment", f"{sleep_disorder_label}{confidence_str}")

                    except Exception as e:
                        st.warning(f"⚠️ Sleep record saved. AI assessment note: {str(e)}")
                        st.success(f"✅ Sleep record saved! Duration: {sleep_duration:.1f} hours")
                else:
                    st.success(f"✅ Sleep record saved! Duration: {sleep_duration:.1f} hours")
                    st.info("💡 Sleep disorder model not available. Install required dependencies for AI predictions.")
            else:
                st.success(f"✅ Sleep record saved! Duration: {sleep_duration:.1f} hours")
                st.info("💡 Sleep disorder model not available. Install required dependencies for AI predictions.")

        st.markdown('</div>', unsafe_allow_html=True)

        # Sleep Analysis & Trends Section
        if st.session_state.get('sleep_data') and len(st.session_state.sleep_data) > 0:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📊 Your Sleep Analytics Dashboard")

            # Use pandas and plotly (already imported at top)
            try:
                import plotly.express as px
            except ImportError:
                st.error("Pandas and Plotly are required for data analysis and charts.")
                # لا يوجد 'return' هنا لتجنب تعديل منطق الكود الأصلي

            if 'pd' in locals() and 'px' in locals():
                sleep_df = pd.DataFrame(st.session_state.sleep_data)

                # Key metrics row
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    avg_duration = sleep_df['duration'].mean()
                    st.metric("Avg Sleep Duration", f"{avg_duration:.1f} hrs",
                                delta=f"{avg_duration - 8:.1f} hrs vs goal" if avg_duration else None)

                with col2:
                    avg_efficiency = sleep_df['efficiency'].mean()
                    st.metric("Avg Sleep Efficiency", f"{avg_efficiency:.1f}%",
                                delta="Good" if avg_efficiency >= 85 else "Fair" if avg_efficiency >= 70 else "Needs Improvement")

                with col3:
                    avg_latency = sleep_df['latency'].mean()
                    st.metric("Avg Time to Sleep", f"{avg_latency:.0f} min",
                                delta="Optimal" if avg_latency <= 15 else "Acceptable" if avg_latency <= 30 else "High")

                with col4:
                    quality_dist = sleep_df['quality'].value_counts()
                    best_quality = quality_dist.idxmax() if len(quality_dist) > 0 else "N/A"
                    st.metric("Most Common Quality", best_quality)

                st.markdown("---")

                # Visualizations
                col_chart1, col_chart2 = st.columns(2)

                with col_chart1:
                    st.markdown("**Sleep Duration Trend**")
                    fig_duration = px.line(
                        x=list(range(1, len(sleep_df) + 1)),
                        y=sleep_df['duration'].values,
                        labels={'x': 'Night', 'y': 'Hours'},
                        markers=True,
                        template='plotly_dark'
                    )
                    fig_duration.add_hline(y=8, line_dash="dash", line_color=SUCCESS,
                                            annotation_text="Recommended: 8 hrs", annotation_position="right")
                    fig_duration.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        hovermode='x unified',
                        margin=dict(l=0, r=0, t=30, b=0)
                    )
                    st.plotly_chart(fig_duration, use_container_width=True, key="sleep_duration_chart")

                with col_chart2:
                    st.markdown("**Sleep Quality Distribution**")
                    quality_order = ["Poor", "Fair", "Good", "Excellent"]
                    quality_counts = sleep_df['quality'].value_counts().reindex(quality_order, fill_value=0)
                    fig_quality = px.bar(
                        x=quality_counts.index,
                        y=quality_counts.values,
                        labels={'x': 'Quality', 'y': 'Count'},
                        color=quality_counts.index,
                        color_discrete_map={"Poor": ERROR, "Fair": WARNING, "Good": ACCENT, "Excellent": SUCCESS},
                        template='plotly_dark'
                    )
                    fig_quality.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        showlegend=False,
                        margin=dict(l=0, r=0, t=30, b=0)
                    )
                    st.plotly_chart(fig_quality, use_container_width=True, key="sleep_quality_chart")

                # Sleep Efficiency and Factors
                col_efficiency, col_factors = st.columns(2)

                with col_efficiency:
                    st.markdown("**Sleep Efficiency Trend**")
                    fig_efficiency = px.line(
                        x=list(range(1, len(sleep_df) + 1)),
                        y=sleep_df['efficiency'].values,
                        labels={'x': 'Night', 'y': 'Efficiency (%)'},
                        markers=True,
                        template='plotly_dark'
                    )
                    fig_efficiency.add_hline(y=85, line_dash="dash", line_color=SUCCESS,
                                            annotation_text="Good Efficiency: 85%", annotation_position="right")
                    fig_efficiency.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        hovermode='x unified',
                        margin=dict(l=0, r=0, t=30, b=0)
                    )
                    st.plotly_chart(fig_efficiency, use_container_width=True, key="sleep_efficiency_chart")

                with col_factors:
                    st.markdown("**Factors Impact Analysis**")
                    activity_impact = sleep_df.groupby('activity_level')['duration'].mean()
                    stress_impact = sleep_df.groupby('stress_level')['duration'].mean()

                    factor_data = pd.concat([
                        pd.DataFrame({'Factor': [f'Activity: {k}' for k in activity_impact.index], 'Avg Sleep': activity_impact.values}),
                        pd.DataFrame({'Factor': [f'Stress: {k}' for k in stress_impact.index], 'Avg Sleep': stress_impact.values})
                    ])

                    fig_factors = px.bar(
                        factor_data,
                        x='Factor',
                        y='Avg Sleep',
                        labels={'Avg Sleep': 'Average Sleep (hrs)'},
                        template='plotly_dark',
                        color='Avg Sleep',
                        color_continuous_scale=[ERROR, WARNING, SUCCESS]
                    )
                    fig_factors.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        showlegend=False,
                        margin=dict(l=0, r=0, t=30, b=0)
                    )
                    st.plotly_chart(fig_factors, use_container_width=True, key="sleep_factors_chart")

            st.markdown('</div>', unsafe_allow_html=True)

        # AI-Powered Recommendations Section
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("💡 AI-Powered Sleep Recommendations")
        st.markdown("---")

        if st.session_state.get('sleep_data') and len(st.session_state.sleep_data) > 0:
            latest_sleep = st.session_state.sleep_data[-1]

            recommendations = []

            # Duration-based recommendations
            if latest_sleep['duration'] < 6:
                recommendations.append(("🛏️ Extend Sleep Duration", "Your recent sleep is below recommended levels. Try going to bed 30 minutes earlier or extending wake time gradually."))
            elif latest_sleep['duration'] > 9:
                recommendations.append(("⏰ Optimize Sleep Duration", "You're sleeping more than recommended. Consider a consistent wake time to regulate your sleep-wake cycle."))
            else:
                recommendations.append(("✅ Sleep Duration Optimal", "Your sleep duration is within the recommended 7-9 hour range. Keep maintaining this!"))

            # Quality-based recommendations
            if latest_sleep['quality'] in ["Poor", "Fair"]:
                recommendations.append(("🌙 Improve Sleep Quality", "Try relaxation techniques 30 minutes before bed: meditation, deep breathing, or light stretching."))

            # Latency-based recommendations
            if latest_sleep['latency'] > 30:
                recommendations.append(("⏳ Reduce Sleep Latency", "Consider limiting screen time 1 hour before bed and establishing a consistent bedtime routine."))

            # Activity and stress-based recommendations
            if latest_sleep['activity_level'] == "Low":
                recommendations.append(("💪 Increase Daytime Activity", "Regular physical activity improves sleep quality. Aim for 30 minutes of moderate activity daily."))

            if latest_sleep['stress_level'] in ["High", "Moderate"]:
                recommendations.append(("😌 Manage Stress", "Practice stress-reduction techniques: journaling, meditation, yoga, or consulting a mental health professional."))

            if not recommendations:
                recommendations.append(("🌟 Keep It Up!", "Your sleep patterns are excellent! Maintain your current sleep hygiene practices."))

            for i, (title, advice) in enumerate(recommendations, 1):
                col_num, col_advice = st.columns([0.3, 2.7])
                with col_num:
                    st.markdown(f"**{i}.**")
                with col_advice:
                    st.markdown(f"**{title}**")
                    st.markdown(f"_{advice}_")
                    st.markdown("")
        else:
            st.info("📝 Start logging your sleep data to receive personalized recommendations from our AI system.")

        st.markdown('</div>', unsafe_allow_html=True)

        # Sleep Hygiene Tips Section
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🌙 Professional Sleep Hygiene Guide")
        st.markdown("---")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**✅ Do's**")
            tips_do = [
                "🕐 Keep consistent bedtime",
                "🌡️ Cool, dark bedroom (65-68°F)",
                "🚶 Light exercise during day",
                "☕ No caffeine after 2 PM",
                "📵 No screens 1 hour before bed",
                "🧘 Practice relaxation techniques"
            ]
            for tip in tips_do:
                st.write(tip)

        with col2:
            st.markdown("**❌ Don'ts**")
            tips_dont = [
                "🛏️ Avoid napping over 30 min",
                "🍺 No alcohol before sleep",
                "🍽️ No heavy meals at night",
                "🎮 Avoid stimulating activities",
                "📺 Don't watch TV in bed",
                "⏰ Don't clock-watch at night"
            ]
            for tip in tips_dont:
                st.write(tip)

        with col3:
            st.markdown("**🎯 Optimization Tips**")
            tips_optimize = [
                "🌞 Get morning sunlight exposure",
                "📅 Track patterns consistently",
                "🧪 Experiment & adjust gradually",
                "🏥 Consult expert if needed",
                "📊 Monitor sleep metrics weekly",
                "🔄 Update goals as needed"
            ]
            for tip in tips_optimize:
                st.write(tip)

        st.markdown('</div>', unsafe_allow_html=True) 

# AI Fitness Trainer Page
elif page == "AI Fitness Trainer":
    st.title("AI Fitness Trainer 💪")
    
    # Initialize YOLO model
    if 'yolo_trainer' not in st.session_state:
        if YOLO_AVAILABLE and YOLOFitnessTrainer is not None:
            try:
                # Use a smaller internal image size to keep the web app smooth
                with st.spinner("Loading AI pose model..."):
                    model_path = os.path.join(BASE_DIR, "yolo11n-pose.pt")
                    st.session_state.yolo_trainer = YOLOFitnessTrainer(
                        model_path=model_path if os.path.exists(model_path) else None,
                        confidence_threshold=0.25,
                        debug=False,
                        imgsz=480,
                    )
                st.success("✅ AI pose model ready!")
            except Exception as e:
                st.error("❌ Could not load the AI pose model. Pose tracking will be disabled.")
                st.session_state.yolo_trainer = None
        else:
            st.session_state.yolo_trainer = None
    
    # Initialize session state
    if 'pose_count' not in st.session_state:
        st.session_state.pose_count = 0
    if 'correct_count' not in st.session_state:
        st.session_state.correct_count = 0
    if 'incorrect_count' not in st.session_state:
        st.session_state.incorrect_count = 0
    if 'form_quality' not in st.session_state:
        st.session_state.form_quality = 'good'
    if 'form_feedback' not in st.session_state:
        st.session_state.form_feedback = ''
    if 'exercise_type' not in st.session_state:
        st.session_state.exercise_type = "Push-ups"
    if 'camera_active' not in st.session_state:
        st.session_state.camera_active = False
    if 'video_file' not in st.session_state:
        st.session_state.video_file = None
    
    # Check AI availability (keep messaging simple for users)
    if not YOLO_AVAILABLE or st.session_state.yolo_trainer is None:
        st.error("⚠️ AI pose tracking is not available on this device.")
        st.warning("You can still use manual rep counting below.")
    else:
        st.success("🤖 AI pose tracking is active – your reps will be counted automatically.")
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🎯 Select Your Exercise")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        exercise_options = ["Push-ups", "Squats", "Plank", "Jumping Jacks", "Burpees"]
        st.session_state.exercise_type = st.selectbox(
            "Choose Exercise Type:",
            exercise_options,
            index=exercise_options.index(st.session_state.exercise_type) if st.session_state.exercise_type in exercise_options else 0
        )
    
    with col2:
        st.markdown('<div class="card" style="padding: 1rem;">', unsafe_allow_html=True)
        st.markdown("### 📊 Live Stats")
        st.metric("Total Reps", st.session_state.pose_count)
        
        # Always show correct/incorrect counts (even if 0)
        col_correct, col_incorrect = st.columns(2)
        with col_correct:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(82,201,162,0.3) 0%, rgba(82,201,162,0.1) 100%);
                padding: 1rem;
                border-radius: 12px;
                border: 2px solid {SUCCESS};
                text-align: center;
            ">
                <div style="font-size: 2rem; font-weight: 800; color: {SUCCESS};">
                    ✅ {st.session_state.correct_count}
                </div>
                <div style="color: {MUTED}; font-size: 0.9rem;">Correct</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_incorrect:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(232,93,117,0.3) 0%, rgba(232,93,117,0.1) 100%);
                padding: 1rem;
                border-radius: 12px;
                border: 2px solid {ERROR};
                text-align: center;
            ">
                <div style="font-size: 2rem; font-weight: 800; color: {ERROR};">
                    ❌ {st.session_state.incorrect_count}
                </div>
                <div style="color: {MUTED}; font-size: 0.9rem;">Incorrect</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Show accuracy if there are any reps
        if st.session_state.pose_count > 0:
            accuracy = (st.session_state.correct_count / st.session_state.pose_count * 100) if st.session_state.pose_count > 0 else 0
            accuracy_color = SUCCESS if accuracy >= 80 else WARNING if accuracy >= 60 else ERROR
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(91,141,239,0.2) 0%, rgba(91,141,239,0.1) 100%);
                padding: 1rem;
                border-radius: 12px;
                border: 2px solid {accuracy_color};
                text-align: center;
                margin-top: 1rem;
            ">
                <div style="font-size: 1.5rem; font-weight: 700; color: {accuracy_color};">
                    {accuracy:.1f}%
                </div>
                <div style="color: {MUTED}; font-size: 0.9rem;">Accuracy</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    exercise_instructions = {
        "Push-ups": "Start in plank position, lower chest to ground, push back up",
        "Squats": "Stand with feet shoulder-width apart, lower hips, stand back up",
        "Plank": "Hold straight body position on forearms and toes",
        "Jumping Jacks": "Jump feet apart while raising arms overhead, return to start",
        "Burpees": "Squat down, jump back to plank, do push-up, jump feet to hands, jump up"
    }
    
    st.info(f"📋 **Instructions:** {exercise_instructions[st.session_state.exercise_type]}")
    
    st.subheader("📹 Live Training Camera")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Live camera feed placeholder
        video_placeholder = st.empty()
        
        if st.session_state.camera_active:
            if YOLO_AVAILABLE and st.session_state.yolo_trainer is not None and cv2 is not None:
                # Continuous webcam capture with YOLO detection
                cap = cv2.VideoCapture(0)
                # Use a slightly smaller resolution to keep the app responsive
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
                cap.set(cv2.CAP_PROP_FPS, 30)

                if not cap.isOpened():
                    st.error("❌ Could not open camera. Make sure it is connected and not used by another app.")
                else:
                    # Process a short burst of frames, then rerun for continuous effect
                    max_frames = 60
                    frames_processed = 0
                    frame_idx = 0  # used for lightweight frame skipping to reduce lag

                    while frames_processed < max_frames and st.session_state.camera_active:
                        # Check if stop button was pressed (check more frequently)
                        if not st.session_state.camera_active:
                            break
                            
                        ret, frame = cap.read()
                        if not ret:
                            break

                        # Flip for mirror view
                        frame = cv2.flip(frame, 1)

                        frame_idx += 1
                        # Run YOLO only on every 2nd frame to reduce CPU/GPU load
                        run_detection = (frame_idx % 2 == 0)

                        if run_detection:
                            # Detect pose
                            pose_result = st.session_state.yolo_trainer.detect_pose(frame)

                            if pose_result["detected"]:
                                rep_completed, count, form_info = st.session_state.yolo_trainer.count_exercise(
                                    pose_result["keypoints"],
                                    st.session_state.exercise_type
                                )

                                # Always update counts from form_info (don't wait for rep completion)
                                # This ensures real-time updates without stopping the app
                                if 'correct_count' in form_info:
                                    st.session_state.correct_count = form_info.get('correct_count', 0)
                                if 'incorrect_count' in form_info:
                                    st.session_state.incorrect_count = form_info.get('incorrect_count', 0)
                                
                                # Update total count only when rep is completed
                                if rep_completed and count > st.session_state.pose_count:
                                    st.session_state.pose_count = count
                                
                                # Update form quality and feedback (always update for real-time feedback)
                                if 'form_quality' in form_info:
                                    st.session_state.form_quality = form_info.get('form_quality', 'good')
                                if 'reason' in form_info:
                                    st.session_state.form_feedback = form_info.get('reason', '')

                                # Draw pose with form indicators
                                frame_with_pose = st.session_state.yolo_trainer.draw_pose(
                                    frame,
                                    pose_result["keypoints"],
                                    pose_result["bbox"],
                                    st.session_state.form_quality
                                )
                                
                                # Add real-time count display on video frame
                                # Show correct and incorrect counts prominently
                                cv2.putText(frame_with_pose, 
                                          f"Total Reps: {st.session_state.pose_count}", 
                                          (10, 30),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                                
                                # Correct count in green
                                cv2.putText(frame_with_pose, 
                                          f"Correct: {st.session_state.correct_count}", 
                                          (10, 70),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                
                                # Incorrect count in red
                                cv2.putText(frame_with_pose, 
                                          f"Incorrect: {st.session_state.incorrect_count}", 
                                          (10, 110),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                
                                # Form quality overlay at bottom
                                form_color = (0, 255, 0) if st.session_state.form_quality == 'good' else (0, 255, 255) if st.session_state.form_quality == 'fair' else (0, 0, 255)
                                cv2.putText(frame_with_pose, 
                                          f"Form: {st.session_state.form_quality.upper()}", 
                                          (10, frame_with_pose.shape[0] - 20),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, form_color, 2)
                                
                                if st.session_state.form_feedback:
                                    cv2.putText(frame_with_pose, 
                                              st.session_state.form_feedback[:50], 
                                              (10, frame_with_pose.shape[0] - 50),
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
                                
                                video_placeholder.image(frame_with_pose, channels="BGR", use_container_width=True)
                            else:
                                # No pose detected - show warning
                                cv2.putText(frame, 
                                          "Position yourself in camera view", 
                                          (10, 30),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                video_placeholder.image(frame, channels="BGR", use_container_width=True)
                        else:
                            # On skipped frames just show the raw frame (no detection) for smoother UI
                            video_placeholder.image(frame, channels="BGR", use_container_width=True)

                        frames_processed += 1
                        # Small delay for smoother display (slightly higher to reduce CPU usage)
                        time.sleep(0.03)

                    cap.release()
                    # Only rerun if camera is still active (stop button not pressed)
                    if st.session_state.camera_active:
                        st.rerun()
                    else:
                        # Camera stopped - show message and don't rerun
                        st.info("⏹️ Training session stopped. Camera released.")
            else:
                st.markdown(f"""
                <div style="
                    border: 3px solid {SUCCESS};
                    border-radius: 20px;
                    padding: 20px;
                    background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
                    text-align: center;
                    color: white;
                    font-weight: bold;
                    margin: 10px 0;
                ">
                    <h3>🎥 Camera Feed (Manual Mode)</h3>
                    <p>Position yourself in front of the camera and use manual controls below</p>
                </div>
                """, unsafe_allow_html=True)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🎬 Start Training", use_container_width=True):
                st.session_state.camera_active = True
                if st.session_state.yolo_trainer is not None:
                    # Reset exercise state
                    st.session_state.yolo_trainer.reset_exercise(st.session_state.exercise_type)
                st.session_state.pose_count = 0
                st.session_state.correct_count = 0
                st.session_state.incorrect_count = 0
                st.session_state.form_quality = 'good'
                st.session_state.form_feedback = ''
                st.success("Camera activated! Position yourself in front of the camera.")
                st.rerun()
        
        with col_btn2:
            if st.button("⏹️ Stop Training", use_container_width=True):
                # Immediately stop the camera loop
                st.session_state.camera_active = False
                st.success("⏹️ Training session stopped. Camera will be released.")
                # Force rerun to stop the camera loop immediately
                st.rerun()
    
    with col2:
        # Keep demos and extra controls in a compact expander so they don't overwhelm the user
        with st.expander("📺 Optional: Exercise Demo Videos & Controls"):
            st.markdown(f"""
            <div style="
                border: 2px solid {ERROR};
                border-radius: 15px;
                padding: 15px;
                background: linear-gradient(135deg, rgba(232,93,117,0.2) 0%, rgba(232,93,117,0.1) 100%);
                text-align: left;
                margin: 10px 0;
            ">
                <h4>Training Library</h4>
                <p style="font-size: 12px; margin: 6px 0;">
                    Place your exercise demo videos in the <code>exercise_videos</code> folder next to <code>LASTO.py</code>.
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Local demo videos from exercise_videos folder – auto-match by exercise
            try:
                local_videos = [
                    f for f in os.listdir(EXERCISE_VIDEO_DIR)
                    if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
                ]
            except Exception:
                local_videos = []

            auto_video_shown = False
            if local_videos:
                # Map exercise type to a preferred filename pattern
                exercise_key = st.session_state.exercise_type.lower()
                preferred_names = {
                    "push-ups": ["pushup", "push-ups", "push_up", "push ups"],
                    "squats": ["squat"],
                    "plank": ["plank"],
                    "jumping jacks": ["jumping_jack", "jumping-jack", "jumping jacks", "jumpingjack"],
                    "burpees": ["burpee", "burpees"],
                }
                patterns = preferred_names.get(exercise_key, [])

                matched_file = None
                # First try exact filenames like pushups.mp4 etc.
                for v in local_videos:
                    name_no_ext = os.path.splitext(v)[0].lower()
                    if name_no_ext == exercise_key.replace(" ", "_") or name_no_ext == exercise_key.replace(" ", ""):
                        matched_file = v
                        break
                # Otherwise try pattern contains
                if matched_file is None and patterns:
                    for v in local_videos:
                        lower_v = v.lower()
                        if any(pat in lower_v for pat in patterns):
                            matched_file = v
                            break

                if matched_file:
                    video_path = os.path.join(EXERCISE_VIDEO_DIR, matched_file)
                    st.caption(f"Demo for **{st.session_state.exercise_type}**: `{matched_file}`")
                    st.video(video_path)
                    auto_video_shown = True

            if not auto_video_shown:
                if local_videos:
                    st.info("Videos found, but none matched this exercise name. "
                            "Rename a file to include the exercise (e.g. `pushups_demo.mp4`).")
                else:
                    st.info("Add demo videos to the `exercise_videos` folder to see them here.")

            uploaded_video = st.file_uploader(
                "Upload Exercise Demo Video (optional)",
                type=['mp4', 'avi', 'mov', 'mkv'],
                help="Upload a demonstration video for the selected exercise"
            )
            
            if uploaded_video is not None:
                st.session_state.video_file = uploaded_video
                st.video(uploaded_video)

            if st.button("🔄 Reset Counter", use_container_width=True):
                st.session_state.pose_count = 0
                st.session_state.correct_count = 0
                st.session_state.incorrect_count = 0
                st.session_state.form_quality = 'good'
                st.session_state.form_feedback = ''
                if st.session_state.yolo_trainer is not None:
                    st.session_state.yolo_trainer.reset_exercise(st.session_state.exercise_type)
                st.success("Counter reset!")
    
    if st.session_state.camera_active:
        st.subheader("🤖 AI Pose Analysis & Form Feedback")
        
        if YOLO_AVAILABLE and st.session_state.yolo_trainer is not None:
            # Form quality indicator
            form_color = SUCCESS if st.session_state.form_quality == 'good' else WARNING if st.session_state.form_quality == 'fair' else ERROR
            form_emoji = "✅" if st.session_state.form_quality == 'good' else "⚠️" if st.session_state.form_quality == 'fair' else "❌"
            
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, {form_color}, {ACCENT_DARK});
                color: white;
                padding: 15px;
                border-radius: 10px;
                text-align: center;
                margin: 10px 0;
            ">
                <strong>{form_emoji} Form Quality: {st.session_state.form_quality.upper()}</strong><br>
                <small>Keep proper posture and full range of motion</small>
            </div>
            """, unsafe_allow_html=True)
            
            # Form feedback
            if st.session_state.form_feedback:
                if st.session_state.form_quality == 'poor':
                    st.warning(f"⚠️ {st.session_state.form_feedback}")
                else:
                    st.info(f"💡 {st.session_state.form_feedback}")
            
            # Always show rep breakdown (even if 0)
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.session_state.pose_count > 0:
                    accuracy = (st.session_state.correct_count / st.session_state.pose_count * 100) if st.session_state.pose_count > 0 else 0
                    st.metric("Accuracy", f"{accuracy:.1f}%")
                else:
                    st.metric("Accuracy", "0%")
            with col2:
                st.metric("✅ Correct Reps", st.session_state.correct_count)
            with col3:
                st.metric("❌ Incorrect Reps", st.session_state.incorrect_count)
        else:
            st.info("🔍 **Manual Mode Active** - Use the buttons below to count your reps")
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if st.button("➕ Count Rep", use_container_width=True):
                    st.session_state.pose_count += 1
                    st.success(f"Great! Rep #{st.session_state.pose_count} completed!")
                    st.rerun()
            
            with col2:
                if st.button("🔄 Reset", use_container_width=True):
                    st.session_state.pose_count = 0
                    st.success("Counter reset!")
                    st.rerun()
            
            with col3:
                if st.button("⏸️ Pause", use_container_width=True):
                    st.session_state.camera_active = False
                    st.info("Training paused!")
                    st.rerun()
        
        # Progress tracking
        target_reps = st.number_input("Set Target Reps", min_value=1, max_value=100, value=10, key="target_reps_input")
        progress = min(st.session_state.pose_count / target_reps, 1.0) if target_reps > 0 else 0
        st.progress(progress)
        st.caption(f"Progress: {st.session_state.pose_count}/{target_reps} reps")
        
        # Show accuracy progress
        if st.session_state.pose_count > 0:
            accuracy = (st.session_state.correct_count / st.session_state.pose_count * 100) if st.session_state.pose_count > 0 else 0
            accuracy_progress = accuracy / 100.0
            st.progress(accuracy_progress, text=f"Form Accuracy: {accuracy:.1f}%")
        
        if st.session_state.pose_count >= target_reps and target_reps > 0:
            st.balloons()
            accuracy = (st.session_state.correct_count / st.session_state.pose_count * 100) if st.session_state.pose_count > 0 else 0
            if accuracy >= 80:
                st.success(f"🎉 Excellent! You've completed {target_reps} reps with {accuracy:.1f}% accuracy!")
            elif accuracy >= 60:
                st.warning(f"🎉 Good job! You've completed {target_reps} reps with {accuracy:.1f}% accuracy. Focus on form!")
            else:
                st.info(f"🎉 You've completed {target_reps} reps, but only {accuracy:.1f}% were correct. Practice proper form!")
    
    st.subheader("💡 Training Tips")
    
    tips_col1, tips_col2 = st.columns(2)
    
    with tips_col1:
        st.markdown("""
        **✅ Good Form Tips:**
        - Keep your core engaged
        - Maintain proper breathing
        - Move through full range of motion
        - Keep movements controlled
        - Position yourself clearly in camera view
        """)
    
    with tips_col2:
        st.markdown("""
        **⚠️ Common Mistakes:**
        - Rushing through movements
        - Partial range of motion
        - Poor posture alignment
        - Holding breath during exercise
        - Not fully completing each rep
        """)
    
    if st.session_state.pose_count > 0:
        st.subheader("📊 Session Summary")
        
        summary_col1, summary_col2, summary_col3 = st.columns(3)
        
        with summary_col1:
            st.metric("Total Reps", st.session_state.pose_count)
        
        with summary_col2:
            st.metric("Exercise Type", st.session_state.exercise_type)
        
        with summary_col3:
            st.metric("Session Status", "Active" if st.session_state.camera_active else "Paused")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Fake News Detection Page
elif page == "Fake News Detection":
    st.title("🩺 Health News Credibility Checker")
    st.markdown("### Analyze health news articles for credibility using advanced AI")
    
    if not is_logged_in():
        st.warning("Please login first to access the Fake News Detection feature.")
        st.info("You can login as a guest to explore the app, but full features require registration.")
    
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Verify Health Information")
        st.write("Paste any health news, article, or claim you want to verify for accuracy and reliability.")
        
        news_input = st.text_area("Enter health news text to analyze:", 
                                 placeholder="Paste the health news article or claim here...", 
                                 height=200)
        
        if st.button("🔍 Verify", type="primary", use_container_width=True):
            if news_input.strip():
                with st.spinner("🤖 Analyzing credibility..."):
                    # Load model
                    classifier = load_fake_news_model()
                    
                    if classifier is None:
                        st.error("❌ Cannot analyze news: Transformers library is not available. Please install it with: `pip install transformers torch`")
                    else:
                        try:
                            # Step 1: AI Classification
                            with st.status("Step 1: AI Classification", expanded=True) as status:
                                st.write("Running zero-shot classification...")
                                candidate_labels = [
                                    "true health information",
                                    "false health information",
                                    "misleading"
                                ]
                                ai_result = classifier(news_input, candidate_labels)
                                if ai_result and 'labels' in ai_result and len(ai_result['labels']) > 0:
                                    st.write(f"✓ Prediction: **{ai_result['labels'][0]}** ({ai_result['scores'][0]*100:.1f}% confidence)")
                                    status.update(label="Step 1: AI Classification ✓", state="complete")
                                else:
                                    st.error("Failed to get classification results")
                                    status.update(label="Step 1: AI Classification ✗", state="error")
                                    ai_result = None
                        except Exception as e:
                            st.error(f"❌ Error during AI classification: {str(e)}")
                            st.info("Please try again or check your internet connection (model download may be required).")
                            ai_result = None
                        
                        if ai_result is None:
                            st.stop()
                        
                        # Step 2: Language Analysis
                        try:
                            with st.status("Step 2: Language Analysis", expanded=True) as status:
                                st.write("Detecting sensational and credible language...")
                                language_analysis = analyze_language(news_input)
                                st.write(f"✓ Sensational words: {language_analysis['sensational_count']}")
                                st.write(f"✓ Credible words: {language_analysis['credible_count']}")
                                status.update(label="Step 2: Language Analysis ✓", state="complete")
                        except Exception as e:
                            st.error(f"❌ Error during language analysis: {str(e)}")
                            language_analysis = {
                                'sensational_words': [],
                                'sensational_count': 0,
                                'credible_words': [],
                                'credible_count': 0
                            }
                        
                        # Step 3: Source Check
                        try:
                            with st.status("Step 3: Source Check", expanded=True) as status:
                                st.write("Checking for trusted sources...")
                                source_check = check_sources(news_input)
                                st.write(f"✓ Trusted sources found: {len(source_check['sources_found'])}")
                                status.update(label="Step 3: Source Check ✓", state="complete")
                        except Exception as e:
                            st.error(f"❌ Error during source check: {str(e)}")
                            source_check = {
                                'sources_found': [],
                                'has_trusted_sources': False
                            }
                        
                        # Final Assessment
                        st.markdown("---")
                        st.markdown("## 📊 Final Assessment")
                        
                        try:
                            final_assessment, confidence_score, assessment_type = get_final_assessment(
                                ai_result, language_analysis, source_check
                            )
                        except Exception as e:
                            st.error(f"❌ Error calculating final assessment: {str(e)}")
                            final_assessment = "⚠️ Analysis incomplete"
                            confidence_score = 0.0
                            assessment_type = "warning"
                        
                        # Display result
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            if assessment_type == "success":
                                st.success(final_assessment)
                            elif assessment_type == "warning":
                                st.warning(final_assessment)
                            else:
                                st.error(final_assessment)
                        
                        with col2:
                            st.metric("Credibility Score", f"{confidence_score:.1f}/100")
                            # Add explanation tooltip
                            with st.expander("ℹ️ What is this score?"):
                                st.markdown("""
                                **Credibility Score (0-100)** represents how credible the information is:
                                - **80-100**: Highly credible (likely true)
                                - **50-79**: Moderately credible (possibly true/misleading)
                                - **20-49**: Low credibility (possibly false)
                                - **0-19**: Very low credibility (likely false)
                                
                                **Calculation:**
                                - **AI Analysis (80%)**: Primary factor based on AI prediction
                                - **Language Analysis (10%)**: Adjustments for credible/sensational words
                                - **Source Check (10%)**: Adjustments for trusted sources
                                """)
                        
                        # Progress bar with color coding
                        progress_value = confidence_score / 100
                        if confidence_score >= 80:
                            progress_color = "#52C9A2"  # Green (high credibility)
                        elif confidence_score >= 50:
                            progress_color = "#F5A623"  # Orange (medium credibility)
                        elif confidence_score >= 20:
                            progress_color = "#E85D75"  # Red (low credibility)
                        else:
                            progress_color = "#E85D75"  # Red (very low credibility)
                        
                        st.progress(progress_value)
                        st.caption(f"Credibility: {'High' if confidence_score >= 80 else 'Medium' if confidence_score >= 50 else 'Low' if confidence_score >= 20 else 'Very Low'}")
                        
                        # Detailed breakdown
                        st.markdown("### 📋 Detailed Breakdown")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**🤖 AI Analysis**")
                            if ai_result and 'labels' in ai_result and len(ai_result['labels']) > 0:
                                for i, (label, score) in enumerate(zip(ai_result['labels'], ai_result['scores'])):
                                    st.write(f"{i+1}. {label}: {score*100:.1f}%")
                            else:
                                st.write("No analysis available")
                        
                        with col2:
                            st.markdown("**📝 Language**")
                            st.write(f"🚨 Sensational: {language_analysis['sensational_count']}")
                            if language_analysis['sensational_words']:
                                st.caption(", ".join(language_analysis['sensational_words'][:5]))
                            st.write(f"✅ Credible: {language_analysis['credible_count']}")
                            if language_analysis['credible_words']:
                                st.caption(", ".join(language_analysis['credible_words'][:5]))
                        
                        with col3:
                            st.markdown("**🏥 Sources**")
                            if source_check['sources_found']:
                                for source in source_check['sources_found'][:5]:
                                    st.write(f"• {source}")
                            else:
                                st.write("No trusted sources mentioned")
                        
                        # Download report
                        st.markdown("---")
                        try:
                            report = generate_fake_news_report(
                                news_input, ai_result, language_analysis, 
                                source_check, final_assessment, confidence_score
                            )
                            
                            st.download_button(
                                label="📥 Download Report",
                                data=report,
                                file_name=f"health_news_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                mime="text/plain",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"❌ Error generating report: {str(e)}")
            else:
                st.warning("⚠️ Please enter some text to analyze.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🔍 How to Spot Fake Health News")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Red Flags to Watch For:**")
            red_flags = [
                "Claims that sound too good to be true",
                "Lack of credible sources or citations",
                "Emotional language designed to create panic",
                "Promises of quick fixes or miracle cures",
                "Information that contradicts established medical knowledge",
                "Use of sensational words like 'miracle', 'secret', 'guaranteed'",
                "Absence of clinical evidence or peer-reviewed studies"
            ]
            for flag in red_flags:
                st.write(f"• {flag}")
        
        with col2:
            st.write("**Trusted Sources:**")
            sources = [
                "World Health Organization (WHO)",
                "Centers for Disease Control (CDC)",
                "National Institutes of Health (NIH)",
                "Food and Drug Administration (FDA)",
                "Peer-reviewed medical journals",
                "Reputable medical institutions",
                "Mayo Clinic, Johns Hopkins"
            ]
            for source in sources:
                st.write(f"• {source}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Disclaimer
        st.markdown("""<div style='background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; border-left: 4px solid #fbbf24; margin-top: 20px;'><strong>🧠 Disclaimer:</strong> This tool assists with analysis and is not a substitute for expert medical verification. Always consult healthcare professionals for medical advice and verify information from multiple trusted sources.</div>""", unsafe_allow_html=True)

# Chatbot Assistant Page
elif page == "Chatbot Assistant":
    check_user_change()
    
    st.title("Chatbot Assistant 🤖")
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Your AI Health Companion")
    st.write("I'm here to help answer your health questions, provide guidance, and offer support. Remember, I'm not a replacement for professional medical advice!")
    
    # Check if we should show fallback mode warning
    if 'api_quota_exceeded' not in st.session_state:
        st.session_state.api_quota_exceeded = False
    
    if st.session_state.api_quota_exceeded:
        st.warning("⚠️ **Fallback Mode Active**: API quota exceeded. Using intelligent rule-based responses. Full AI features will resume when quota resets.")

    tone = st.radio("Select Chatbot Tone", ["Supportive", "Motivational", "Scientific"], horizontal=True)
    st.session_state["chatbot_tone"] = tone
    
    st.write("**Quick Actions:**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💡 Health Tips", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": "Give me some health tips"})
            response = generate_chatbot_response("Give me some health tips", st.session_state.user_data)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col2:
        if st.button("🍎 Nutrition Advice", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": "Give me nutrition advice"})
            response = generate_chatbot_response("Give me nutrition advice", st.session_state.user_data)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col3:
        if st.button("💪 Exercise Help", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": "Give me exercise advice"})
            response = generate_chatbot_response("Give me exercise advice", st.session_state.user_data)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**💬 Chat with AURA**")
    with col2:
        if st.button("🗑️ Clear Chat", help="Clear all chat messages", type="secondary", use_container_width=True):
            st.session_state.chat_history = []
            st.success("Chat cleared! 🗑️")
            st.rerun()
    
    if st.session_state.chat_history:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    else:
        st.info("👋 Hi! I'm AURA, your AI Wellness Guardian. Ask me anything about health, nutrition, exercise, or wellness!")

    user_input = st.chat_input("Ask me anything about health, nutrition, exercise, or wellness...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                time.sleep(1)
            
            response = generate_chatbot_response(user_input, st.session_state.user_data)
            st.markdown(response)
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    st.markdown('</div>', unsafe_allow_html=True)

# Default case - if page doesn't match any condition
else:
    try:
        st.title("Page Not Found")
        st.info(f"Page '{page}' is not available. Please select a valid page from the navigation.")
        try:
            if 'pages' in locals() or 'pages' in globals():
                st.markdown(f"**Available pages:** {', '.join(pages)}")
        except:
            pass
    except Exception as e:
        st.error(f"⚠️ An error occurred: {str(e)}")

st.sidebar.markdown("---")
