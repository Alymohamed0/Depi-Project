# AI Wellness Guardian 🌟

A comprehensive AI-powered health and wellness platform that combines physical and mental health monitoring, personalized recommendations, and intelligent health information verification.

## 🎯 Features

### Core Functionality
- **Profile Registration**: Complete user profile with BMI calculation and target calorie setting
- **Health Recommendations**: Personalized diet, exercise, and sleep plans for Bulk/Cutting modes
- **Mood Detection**: AI-powered sentiment analysis with personalized activity suggestions
- **Sleep Analysis**: Comprehensive sleep tracking with trends and optimization tips
- **Fake News Detection**: Health information verification and credibility scoring
- **AI Chatbot**: Intelligent health assistant with personalized responses
- **Dashboard**: Real-time health metrics and insights visualization

### AI Models Integration
- **Calorie Prediction**: Uses trained GradientBoostingRegressor for accurate calorie estimation
- **Meal Classification**: Integrates RandomForest model for meal type recommendations
- **Sentiment Analysis**: TextBlob-powered mood detection with fallback algorithms
- **Health Information Verification**: Pattern-based fake news detection

## 🚀 Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ai-wellness-guardian
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run frontend.py
   ```

4. **Open your browser**
   Navigate to `http://localhost:8501`

### Prerequisites
- Python 3.8+
- Required model files in the project directory:
  - `calories_model.joblib`
  - `feature_bounds.joblib`
  - `best_meal_model.pkl`

## 📱 Usage Guide

### 1. Profile Registration
- Enter your basic information (age, weight, height, gender)
- Select your health goal (Bulk Mode for weight gain, Cutting Mode for weight loss)
- View calculated BMI and target calories

### 2. Health Recommendations
- Get personalized diet plans based on your mode
- Use the food calorie calculator with AI predictions
- Track exercise sessions and receive workout recommendations
- Log sleep data and get optimization tips

### 3. Mood Detection
- Describe your current mood or feelings
- Receive AI-powered sentiment analysis
- Get personalized activity suggestions
- View mood trends over time

### 4. Sleep Analysis
- Log detailed sleep information
- View comprehensive sleep analytics
- Set sleep goals and track progress
- Receive optimization recommendations

### 5. Fake News Detection
- Paste health news or information for verification
- Get reliability scores and credibility analysis
- Learn to identify fake health information
- Access trusted health sources

### 6. AI Chatbot
- Ask health-related questions
- Get personalized advice based on your profile
- Use quick action buttons for common topics
- Access comprehensive health knowledge base

### 7. Dashboard
- View daily health metrics
- Track progress with visualizations
- Get AI-powered health insights
- Quick access to all features

## 🛠️ Technical Architecture

### Frontend
- **Streamlit**: Modern web application framework
- **Plotly**: Interactive data visualizations
- **Custom CSS**: Dark theme with modern UI/UX

### Backend
- **Scikit-learn**: Machine learning models
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations
- **TextBlob**: Natural language processing

### Data Storage
- **Session State**: In-memory data persistence
- **CSV Integration**: Data import/export capabilities

## 📊 Model Details

### Calorie Prediction Model
- **Algorithm**: GradientBoostingRegressor
- **Features**: serving_size, protein, carbs, fat, food_group, serving_unit
- **Accuracy**: R² score with cross-validation
- **Usage**: Real-time calorie estimation for food items

### Meal Classification Model
- **Algorithm**: RandomForestClassifier
- **Features**: nutritional content and meal type
- **Purpose**: Vegetarian/non-vegetarian meal recommendations
- **Integration**: Bulk/Cutting mode meal planning

### Mood Analysis
- **Primary**: TextBlob sentiment analysis
- **Fallback**: Keyword-based sentiment detection
- **Output**: Sentiment polarity and mood classification
- **Features**: Personalized activity recommendations

## 🎨 UI/UX Features

### Design
- **Dark Theme**: Modern, eye-friendly interface
- **Responsive Layout**: Works on desktop and mobile
- **Interactive Elements**: Hover effects and animations
- **Color Coding**: Intuitive health status indicators

### User Experience
- **Intuitive Navigation**: Clear sidebar menu
- **Progress Tracking**: Visual progress bars and metrics
- **Real-time Feedback**: Instant AI responses
- **Data Visualization**: Interactive charts and graphs

## 🔧 Configuration

### Environment Variables
No environment variables required for basic functionality.

### Model Files
Ensure the following model files are present:
- `calories_model.joblib`: Calorie prediction model
- `feature_bounds.joblib`: Feature scaling bounds
- `best_meal_model.pkl`: Meal classification model

### Optional Dependencies
- `textblob`: Enhanced mood analysis (fallback available)
- `streamlit-lottie`: Animated elements (optional)

## 📈 Health Metrics Tracked

### Physical Health
- Daily calorie intake vs. target
- Water consumption
- Exercise duration and type
- Sleep duration and quality
- BMI and weight management

### Mental Health
- Mood sentiment analysis
- Stress level indicators
- Activity recommendations
- Mental wellness tips

### Sleep Health
- Sleep duration and efficiency
- Bedtime and wake time patterns
- Sleep quality ratings
- Optimization recommendations

## 🛡️ Safety & Disclaimers

### Medical Disclaimer
- This application provides general health information only
- Not a replacement for professional medical advice
- Consult healthcare professionals for medical conditions
- Emergency situations require immediate medical attention

### Data Privacy
- All data stored locally in session state
- No external data transmission
- User data not persisted between sessions
- Privacy-focused design

## 🚀 Future Enhancements

### Planned Features
- User authentication and data persistence
- Advanced AI model integration
- Real-time health monitoring
- Social features and community support
- Mobile app development
- Integration with wearable devices

### Model Improvements
- Enhanced mood detection algorithms
- Advanced fake news detection
- Personalized recommendation engine
- Predictive health analytics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Streamlit team for the excellent framework
- Scikit-learn community for machine learning tools
- Plotly for interactive visualizations
- TextBlob for natural language processing

## 📞 Support

For support, questions, or feature requests:
- Create an issue in the repository
- Contact the development team
- Check the documentation

---

**AI Wellness Guardian** - Your smart health companion for a better tomorrow! 🌟


