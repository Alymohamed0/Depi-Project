# AI Wellness Guardian 🌟

A comprehensive AI-powered health and wellness platform that combines physical and mental health monitoring, personalized recommendations, intelligent health information verification, and real-time fitness tracking with pose detection.

## 🎯 Features

### Core Functionality
- **User Authentication**: Secure login system with MySQL database integration and guest mode
- **Profile Registration**: Complete user profile with BMI calculation, target calorie setting, and health metrics
- **Smart Health & Fitness Plan**: AI-generated personalized plans for diet, exercises, equipment, and fitness type
- **AI Fitness Trainer**: Real-time pose detection and exercise counting using YOLOv11
  - Supports: Push-ups, Squats, Planks, Jumping Jacks, Burpees
  - Form validation and real-time feedback
  - Correct/incorrect rep tracking
- **Health Recommendations**: Personalized diet, exercise, and sleep plans for Bulk/Cutting modes
- **Meal Logger**: Track daily nutrition with AI-powered meal classification
- **Mood Detection**: AI-powered sentiment analysis using Transformers (RoBERTa) with personalized activity suggestions
- **Sleep Analysis**: Comprehensive sleep tracking with AI disorder detection and optimization tips
- **Fake News Detection**: Health information verification using BART zero-shot classification with credibility scoring
- **AI Chatbot (AURA)**: Intelligent health assistant powered by Google Gemini with personalized responses
- **Dashboard**: Real-time health metrics, progress tracking, and insights visualization
- **Daily Tracker**: Track water intake, calories, exercise, and mood
- **Progress & Goals**: Weight tracking, goal setting, and weekly activity overview
- **Health Journal**: Personal health journaling with tags and mood tracking

### AI Models Integration
- **Smart Health Plan Models**: 
  - Diet recommendation model
  - Exercise recommendation model
  - Equipment recommendation model
  - Fitness type classification
  - General health recommendations
- **Meal Classification**: RandomForest pipeline for diet type classification (paleo, vegan, keto, mediterranean, dash)
- **Calorie Prediction**: Feature-based calorie estimation from macronutrients
- **Mood Detection**: RoBERTa-based emotion classification (27 emotions) with fallback to TextBlob
- **Sleep Disorder Detection**: RandomForest model for sleep pattern analysis
- **Fake News Detection**: BART zero-shot classification with language analysis and source verification
- **Pose Detection**: YOLOv11 pose estimation for real-time exercise tracking

## 🚀 Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "The Project #F"
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables** (Optional)
   Create a `cursor.env` file or set environment variable:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

4. **Database Setup** (Optional)
   - Install MySQL server
   - The app will auto-initialize the database on first use
   - Default connection: localhost, user: root
   - Database name: `wellness_db`

5. **Run the application**
   ```bash
   streamlit run LASTO.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:8501`

### Prerequisites
- Python 3.8+
- Webcam (for AI Fitness Trainer)
- MySQL (optional, for data persistence)

### Required Model Files
Ensure the following model files are present in the project directory:
- **Health Plan Models**:
  - `Diet_model.joblib` & `Diet_output_encoder.joblib`
  - `Exercises_model.joblib` & `Exercises_output_encoder.joblib`
  - `Equipment_model.joblib` & `Equipment_output_encoder.joblib`
  - `Fitness Type_model.joblib` & `Fitness Type_output_encoder.joblib`
  - `Recommendation_model.joblib` & `Recommendation_output_encoder.joblib`
- **Input Encoders**:
  - `Sex_input_encoder.joblib`
  - `Level_input_encoder.joblib`
  - `Fitness Goal_input_encoder.joblib`
  - `Hypertension_input_encoder.joblib`
  - `Diabetes_input_encoder.joblib`
- **Other Models**:
  - `best_random_model.pkl` (Sleep disorder detection)
  - `food_pipeline.joblib` (Meal classification)
  - `diet_label_encoder.joblib` (Diet labels)
  - `yolo11n-pose.pt` (Pose detection - auto-downloads if missing)
- **Data Files**:
  - `All_Diets.csv` (Food database)
  - `expanded_sleep_health_dataset.csv` (Sleep data)

## 📱 Usage Guide

### 1. Login & Registration
- **Login**: Use existing credentials or demo accounts (admin/admin123, user/user123, demo/demo123)
- **Register**: Create a new account with username and password
- **Guest Mode**: Explore the app without registration (limited features)

### 2. Profile Registration
- Enter your basic information (age, weight, height, gender)
- Select your health goal (Bulk Mode for weight gain, Cutting Mode for weight loss)
- Set physical activity level and stress level
- View calculated BMI, BMI category, and target calories
- Profile data is saved to MySQL database (if available)

### 3. Smart Health & Fitness Plan
- Provide additional health information (hypertension, diabetes)
- Click "Generate My Complete Health Plan"
- Receive AI-generated personalized recommendations for:
  - **General Health Recommendation**: Overall wellness guidance
  - **Diet Recommendation**: Personalized food items and meal suggestions
  - **Fitness Type**: Recommended workout style
  - **Exercises**: Specific exercises tailored to your profile
  - **Required Equipment**: Equipment needed for your plan

### 4. AI Fitness Trainer 💪
- Select exercise type: Push-ups, Squats, Planks, Jumping Jacks, or Burpees
- Click "Start Training" to activate webcam
- Position yourself in front of the camera
- AI tracks your form and counts reps automatically
- Real-time feedback on:
  - Form quality (Good/Fair/Poor)
  - Correct vs incorrect reps
  - Form improvement suggestions
- View exercise demo videos (place in `exercise_videos/` folder)
- Set target reps and track progress

### 5. Health Recommendations
- **Food Recommendations**: 
  - Select diet preferences (paleo, vegan, keto, mediterranean, dash)
  - Get AI-recommended meals based on your goals
  - Add and classify new meals with AI
- **Training Plans**: Get personalized workout recommendations
- **Exercise Logging**: Track your workout sessions

### 6. Meal Logger
- Log meals with nutritional information
- Track calories, protein, carbs, and fats
- View daily nutrition summary
- Macronutrient distribution charts

### 7. Mood Detection
- Describe your current mood or feelings
- Receive AI-powered emotion analysis (27 emotions)
- Get personalized activity suggestions based on mood
- View mood trends over time
- Access mood-boosting activity recommendations

### 8. Sleep Analysis
- Log detailed sleep information:
  - Bedtime and wake time
  - Sleep latency (time to fall asleep)
  - Number of awakenings
  - Sleep quality rating
  - Activity and stress levels
- View comprehensive sleep analytics:
  - Sleep duration trends
  - Sleep efficiency tracking
  - Quality distribution
  - Factors impact analysis
- Receive AI-powered sleep disorder assessment
- Get personalized optimization recommendations
- Access professional sleep hygiene guide

### 9. Fake News Detection
- Paste health news or information for verification
- Get comprehensive credibility analysis:
  - AI classification (true/misleading/false)
  - Language analysis (sensational vs credible words)
  - Source verification (trusted sources check)
  - Final credibility score (0-100)
- Download detailed analysis report
- Learn to identify fake health information
- Access trusted health sources list

### 10. AI Chatbot Assistant (AURA)
- Ask health-related questions
- Get personalized advice based on your profile
- Three conversation tones: Supportive, Motivational, Scientific
- Quick action buttons for common topics
- Context-aware responses using conversation history
- Powered by Google Gemini (free models with automatic fallback)

### 11. Dashboard
- View daily health metrics and profile summary
- Track progress with interactive visualizations
- Quick access to all features
- Health trends and insights

### 12. Daily Tracker
- Log daily water intake, calories, exercise, and mood
- Track progress toward daily goals
- View health score calculation
- See achievements and badges

### 13. Progress & Goals
- Set daily goals (water, exercise, sleep, calories)
- Log and track weight progress over time
- View weekly activity overview
- Monitor progress with visual charts

### 14. Health Journal
- Write journal entries with date and title
- Track energy level and overall mood
- Add tags (Exercise, Nutrition, Sleep, Stress, etc.)
- View journal history with sorting

## 🛠️ Technical Architecture

### Frontend
- **Streamlit**: Modern web application framework with reactive UI
- **Plotly**: Interactive data visualizations and charts
- **Custom CSS**: Beautiful dark theme with glassmorphism effects, animations, and modern UI/UX
- **OpenCV**: Video processing for fitness trainer

### Backend
- **Scikit-learn**: Machine learning models (RandomForest, GradientBoosting)
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations
- **Transformers (Hugging Face)**: Advanced NLP models for mood and fake news detection
- **TextBlob**: Natural language processing (fallback for mood detection)
- **Google Generative AI**: Gemini API for chatbot
- **Ultralytics YOLO**: YOLOv11 pose estimation model
- **MySQL Connector**: Database integration for user data persistence

### Data Storage
- **MySQL Database**: User profiles, authentication, and persistent data
- **Session State**: In-memory data persistence for active sessions
- **CSV Files**: Food database and sleep dataset
- **Joblib/Pickle**: Trained ML models and encoders

## 📊 Model Details

### Smart Health Plan Models
- **Diet Model**: Recommends personalized food items based on user profile
- **Exercises Model**: Suggests specific exercises for fitness goals
- **Equipment Model**: Recommends required equipment
- **Fitness Type Model**: Classifies recommended workout style
- **Recommendation Model**: Provides general health guidance
- **Input Features**: Gender, age, height, weight, BMI, BMI category, fitness goal, hypertension, diabetes

### Meal Classification Model
- **Algorithm**: RandomForest Pipeline
- **Features**: Protein, Carbs, Fat (with derived features)
- **Output**: Diet type classification (paleo, vegan, keto, mediterranean, dash)
- **Usage**: Real-time meal classification and food recommendations

### Mood Detection Model
- **Primary**: RoBERTa-base-go-emotions (Hugging Face)
- **Fallback**: TextBlob sentiment analysis
- **Output**: 27 emotion classifications with confidence scores
- **Features**: Personalized activity recommendations based on detected emotions

### Sleep Disorder Detection Model
- **Algorithm**: RandomForest
- **Features**: Sleep duration, quality, latency, awakenings, activity level, stress level
- **Output**: Sleep disorder risk assessment
- **Usage**: Sleep pattern analysis and health recommendations

### Fake News Detection Model
- **Algorithm**: BART-large-MNLI (Zero-shot classification)
- **Features**: Text analysis, language patterns, source verification
- **Output**: Credibility score (0-100) with detailed breakdown
- **Usage**: Health information verification

### Pose Detection Model
- **Model**: YOLOv11-nano-pose
- **Framework**: Ultralytics YOLO
- **Features**: 17 keypoint detection (COCO format)
- **Usage**: Real-time exercise form analysis and rep counting
- **Supported Exercises**: Push-ups, Squats, Planks, Jumping Jacks, Burpees

## 🎨 UI/UX Features

### Design
- **Modern Dark Theme**: Eye-friendly dark background with gradient animations
- **Glassmorphism**: Beautiful frosted glass effects with backdrop blur
- **Responsive Layout**: Works seamlessly on desktop and mobile
- **Interactive Elements**: Hover effects, smooth animations, and transitions
- **Color Coding**: Intuitive health status indicators (green/yellow/red)
- **Gradient Backgrounds**: Animated gradients for visual appeal
- **Card-based Layout**: Modern card design with shadows and borders

### User Experience
- **Intuitive Navigation**: Clear sidebar menu with icons
- **Progress Tracking**: Visual progress bars, gauges, and metrics
- **Real-time Feedback**: Instant AI responses and form validation
- **Data Visualization**: Interactive charts and graphs (Plotly)
- **Loading States**: Smooth loading indicators and spinners
- **Error Handling**: Graceful error messages and fallbacks
- **Accessibility**: Clear typography and color contrast

## 🔧 Configuration

### Environment Variables
Create a `cursor.env` file or set environment variable:
```bash
GEMINI_API_KEY=your_google_gemini_api_key
```

The app will automatically try multiple free Gemini models:
1. gemini-2.5-flash
2. gemini-2.5-flash-lite
3. gemini-2.0-flash
4. gemini-1.5-flash
5. gemini-1.5-pro

### Database Configuration
Default MySQL settings (can be modified in `get_database_connection()`):
- Host: localhost
- User: root
- Database: wellness_db
- Auto-initialization on first use

### Optional Dependencies
- **transformers**: Enhanced mood detection (auto-downloads models)
- **torch**: Required for Transformers models
- **streamlit-lottie**: Animated elements (optional)
- **opencv-python**: Required for AI Fitness Trainer
- **ultralytics**: Required for YOLO pose detection

## 📈 Health Metrics Tracked

### Physical Health
- Daily calorie intake vs. target
- Water consumption (glasses)
- Exercise duration and type
- Sleep duration, quality, and efficiency
- BMI and weight management
- Exercise form quality and rep accuracy

### Mental Health
- Mood sentiment analysis (27 emotions)
- Stress level indicators
- Activity recommendations based on mood
- Mental wellness tips and journaling

### Sleep Health
- Sleep duration and efficiency
- Bedtime and wake time patterns
- Sleep latency (time to fall asleep)
- Number of awakenings
- Sleep quality ratings
- AI-powered sleep disorder assessment

### Fitness Tracking
- Exercise rep counting
- Form quality assessment
- Correct vs incorrect rep tracking
- Exercise accuracy percentage
- Real-time pose feedback

## 🛡️ Safety & Disclaimers

### Medical Disclaimer
- This application provides general health information and lifestyle guidance only
- **Not a replacement for professional medical advice, diagnosis, or treatment**
- Consult qualified healthcare professionals for medical conditions
- Emergency situations require immediate medical attention
- The AI chatbot (AURA) is designed for wellness support, not medical diagnosis

### Data Privacy
- User authentication data stored securely in MySQL database
- Session data stored locally in Streamlit session state
- No external data transmission except for:
  - Google Gemini API (chatbot queries)
  - Hugging Face model downloads (mood detection, fake news)
- User can use guest mode for privacy
- All data can be cleared by logging out

### AI Model Limitations
- Pose detection requires good lighting and clear camera view
- Exercise counting accuracy depends on proper form and camera angle
- AI recommendations are suggestions, not medical prescriptions
- Fake news detection provides analysis, not absolute truth

## 🚀 Future Enhancements

### Planned Features
- ✅ User authentication and data persistence (Implemented)
- ✅ AI Fitness Trainer with pose detection (Implemented)
- ✅ Advanced AI model integration (Implemented)
- 🔄 Real-time health monitoring with wearables
- 🔄 Social features and community support
- 🔄 Mobile app development
- 🔄 Integration with fitness trackers
- 🔄 Meal photo recognition
- 🔄 Voice commands for chatbot

### Model Improvements
- Enhanced mood detection with more emotions
- Advanced fake news detection with fact-checking
- Personalized recommendation engine improvements
- Predictive health analytics
- Multi-person pose detection for group workouts

## 📦 Project Structure

```
The Project #F/
├── LASTO.py                      # Main application file
├── yolo_fitness_model.py         # YOLO pose detection module
├── requirements.txt              # Python dependencies
├── cursor.env                    # Environment variables (API keys)
├── README.md                     # This file
│
├── Models/                       # ML model files
│   ├── Diet_model.joblib
│   ├── Exercises_model.joblib
│   ├── Equipment_model.joblib
│   ├── Fitness Type_model.joblib
│   ├── Recommendation_model.joblib
│   ├── best_random_model.pkl
│   ├── food_pipeline.joblib
│   └── ... (encoders)
│
├── Data/
│   ├── All_Diets.csv            # Food database
│   └── expanded_sleep_health_dataset.csv
│
└── exercise_videos/             # Demo videos for exercises
    ├── pushups_demo.mp4
    ├── squats_demo.mp4
    └── ...
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Streamlit** team for the excellent framework
- **Google DeepMind** for Gemini API
- **Ultralytics** for YOLOv11 pose detection
- **Hugging Face** for Transformers models
- **Scikit-learn** community for machine learning tools
- **Plotly** for interactive visualizations
- **TextBlob** for natural language processing

## 📞 Support

For support, questions, or feature requests:
- Create an issue in the repository
- Check the documentation
- Review the code comments for implementation details

## 🎯 Key Highlights

- 🌟 **Comprehensive Health Platform**: All-in-one solution for physical and mental wellness
- 🤖 **Advanced AI Integration**: Multiple ML models working together
- 💪 **Real-time Fitness Tracking**: Pose detection with form analysis
- 🧠 **Intelligent Recommendations**: Personalized plans based on your profile
- 🛡️ **Health Information Verification**: Fake news detection for safe health information
- 📊 **Data-Driven Insights**: Visual analytics and progress tracking
- 🎨 **Beautiful Modern UI**: Professional design with smooth animations

---

**AI Wellness Guardian** - Your smart health companion for a better tomorrow! 🌟

*Powered by AI • Built with ❤️ for your wellness*
