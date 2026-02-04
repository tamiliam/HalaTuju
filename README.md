# 🎓 HalaTuju: SPM Leaver Course Recommender

HalaTuju is an AI-powered analytics and recommendation platform designed to help SPM (Sijil Pelajaran Malaysia) leavers navigate their post-secondary education options. It aggregates data from Polytechnics, Community Colleges, TVET institutions (ILKBS, ILJTM), and Public Universities (IPTA) to provide personalized course matching based on academic results, interests, and career aspirations.

## 📊 Course Coverage

- **814+ Courses** across multiple pathways:
  - Polytechnics (Diploma programs)
  - Community Colleges (Certificate & Diploma programs)
  - TVET Institutions (ILKBS, ILJTM vocational training)
  - **Public Universities (87 Asasi/Foundation programs from 20 IPTA)**

## 🚀 Key Features

-   **Smart Eligibility Engine**: Automatically checks student grades against thousands of course requirements:
    -   Polytechnic/KK/TVET: General & Specific rules
    -   **University (IPTA): Grade B requirements, Distinction requirements (A-), Complex OR-group logic**
-   **Holistic Ranking System**: Ranks eligible courses using a weighted scoring model that considers:
    -   Academic Fit
    -   Interest Alignment (based on RIASEC/Holland Code)
    -   Work & Learning Preferences (Hands-on vs. Theory)
    -   Physical & Environmental Constraints
-   **Interactive Dashboard**: Visualizes top matches, providing deep insights into why a course is a good fit.
-   **AI-Powered Reports**: Generates personalized PDF reports using Google Gemini (with OpenAI fallback) to explain career pathways.
-   **Multi-Language Support**: Fully localized interface in English, Bahasa Melayu, and Tamil.
-   **Robust Auth & Persistence**: Secure user accounts and profile storage via Supabase.

## 📂 Project Structure

```
HalaTuju/
├── assets/                 # Static assets (CSS, Images)
├── data/                   # Data sources (Courses, Requirements CSVs)
├── docs/                   # Documentation files
├── scripts/                # Utility scripts
├── src/                    # Source Code
│   ├── auth.py             # User Authentication logic
│   ├── dashboard.py        # Streamlit Dashboard UI logic
│   ├── engine.py           # Core Eligibility Engine
│   ├── ranking_engine.py   # Course Ranking & Scoring Algorithm
│   ├── quiz_manager.py     # Personality/Interest Quiz Logic
│   ├── translations.py     # Localization/Translation Strings
│   └── reports/            # AI & PDF Reporting Modules
├── tests/                  # Unit & Regression Tests
├── main.py                 # Application Entry Point
└── requirements.txt        # Python Dependencies
```

## 🛠️ Prerequisites

-   **Python 3.10+** (Recommended)
-   **Supabase Account**: For authentication and database.
-   **Google Gemini API Key**: For the primary AI features.
-   **OpenAI API Key** (Optional): For fallback AI support.

## 📥 Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/tamiliam/HalaTuju.git
    cd HalaTuju
    ```

2.  **Create a Virtual Environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Secrets**
    Create a `.streamlit/secrets.toml` file in the project root:
    ```toml
    # .streamlit/secrets.toml

    SUPABASE_URL = "your_supabase_url"
    SUPABASE_KEY = "your_supabase_anon_key"
    GEMINI_API_KEY = "your_gemini_api_key"
    OPENAI_API_KEY = "your_openai_key"  # Optional
    ```

5.  **Run the Application**
    ```bash
    streamlit run main.py
    ```

## 🧪 Testing

The project maintains a **Golden Master** test suite to ensure the integrity of the eligibility engine.

Run the tests using:
```bash
python -m unittest tests/test_golden_master.py
```

## 📝 License

Internal / Proprietary.
