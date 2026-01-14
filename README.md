# 🏗️ Procurement Intelligence Portal

A **Procurement Intelligence Portal** is a modular data analytics platform designed to support **strategic, tactical, and operational decision-making** in purchasing and supply management.

This project was built both as:

* A **real-world solution** for procurement departments
* A **professional showcase** of data analytics, business intelligence, and data engineering skills for international markets

---

## 🎯 Business Problem

Procurement teams commonly face challenges such as:

* Lack of visibility over total spend
* Difficulty identifying savings opportunities
* Supplier fragmentation and price inconsistency
* Compliance risks (taxes, fiscal rules, contracts)
* Data scattered across invoices and ERP exports

This portal centralizes purchasing data and transforms it into **actionable insights**.

---

## 💡 Solution Overview

The platform consolidates purchasing transactions into a single analytical environment, offering:

* **Spend Analysis** by product, category, supplier, and time
* **Executive KPIs** for decision-makers
* **Compliance validation** at item level
* **Supplier analytics** and negotiation insights
* **Operational search** for day-to-day purchasing support

The solution is built with scalability and maintainability in mind, following a **clean, modular architecture**.

---

## 🧱 Architecture & Tech Stack

### Core Technologies

* **Python** – data processing and business logic
* **Pandas** – transformations and aggregations
* **SQLite** – analytical database (easily replaceable by PostgreSQL / SQL Server)
* **Streamlit** – interactive BI and dashboard layer

### Architectural Principles

* Separation of concerns (UI, business rules, data layer)
* Centralized data preprocessing
* Reusable analytical functions
* Single source of truth for all dashboards

---

## 📁 Project Structure

```
portal_suprimentos/
│
├── app.py                      # Main application orchestrator
├── compras_suprimentos.db      # Analytical database
│
├── styles/
│   └── theme.py                # UI theme and visual identity
│
├── utils/
│   ├── classifiers.py          # Smart material categorization
│   ├── normalizer.py           # Unit normalization logic
│   ├── formatters.py           # Currency and percentage formatting
│   └── compliance.py           # Compliance and validation rules
│
├── ui/
│   ├── tab_exec_review.py      # Executive overview
│   ├── tab_dashboard.py        # Tactical analytics dashboard
│   ├── tab_compliance.py       # Compliance monitoring
│   ├── tab_fornecedores.py     # Supplier management
│   ├── tab_negociacao.py       # Negotiation & savings cockpit
│   └── tab_busca.py            # Operational search
│
└── extrator.py                 # Data ingestion and ETL pipeline
```

---

## 📊 Application Tabs

### 📌 Executive Overview

* High-level KPIs
* Annual spend analysis
* Management-oriented language

### 📊 Dashboard

* Tactical analysis
* Category and product drill-down
* Trend identification

### 🛡️ Compliance

* Item-level compliance validation
* Fiscal and operational risk detection
* Audit support

### 📇 Supplier Management

* Consolidated supplier spend
* Historical price tracking
* **Supplier performance scoring (Supplier Score)**
* Data-driven insights to support supplier selection and negotiation

### 💰 Negotiation Cockpit

* Lowest historical price per item
* Latest supplier comparison
* Potential savings calculation

### 🔍 Search

* Fast operational lookup
* Supports buyers in daily activities

---

## 🧠 Data Intelligence Layer

Key analytical features include:

* Date normalization and temporal dimensions
* Product description standardization
* Unit of measure normalization
* Automated category classification
* Consolidated tax calculation
* Savings potential estimation

### Supplier Scoring Model

The platform includes an **implemented supplier scoring model**, designed to support sourcing, negotiation, and supplier management decisions.

The score consolidates multiple dimensions into a single, actionable indicator:

* **Price performance** – historical unit prices and competitiveness
* **Compliance status** – fiscal and operational conformity
* **Spend relevance & stability** – volume and consistency over time
* **Lead Time (Delivery Performance)** – average delivery time in days

When ERP delivery data is unavailable, **lead time is captured through user-validated operational input**, reflecting real-world procurement workflows. This approach ensures the model remains practical, accurate, and aligned with how procurement teams actually operate.

### How the Supplier Score is Used

The Supplier Score is not a static metric; it is designed as a **decision-support tool** embedded directly into procurement workflows.

Typical use cases include:

* **Supplier comparison** – Quickly identifying the most competitive and reliable suppliers for a given category or item
* **Negotiation preparation** – Supporting discussions with objective performance data (price history, delivery performance, compliance)
* **Risk awareness** – Highlighting suppliers with compliance or delivery risks
* **Sourcing prioritization** – Guiding buyers toward suppliers that combine cost efficiency and operational reliability

By placing the score **directly alongside each supplier**, the platform reduces analytical friction and enables faster, data-driven decisions at both operational and strategic levels.

All intelligence is applied **before** data reaches the dashboards, ensuring consistency across the application.

---

## 🌍 International Readiness

The project is designed to be easily:

* Translated to English (UI and metrics)
* Migrated to cloud databases
* Extended into a SaaS model
* Integrated with ERP exports (CSV / SQL)

It demonstrates capabilities aligned with roles such as:

* Data Analyst
* BI Analyst
* Analytics Engineer (Junior–Mid)
* Procurement Analytics Consultant

---

## 🚀 Future Improvements

* Full internationalization (EN)
* Automated ETL scheduling
* Supplier scoring model
* Price prediction using machine learning
* Cloud deployment (AWS / GCP / Azure)

---

## 👤 Author

Developed by **Lucas Lima** as a professional portfolio project focused on **data-driven procurement solutions**.

If you are interested in collaboration, consulting, or analytics-driven procurement solutions, feel free to connect.

---

## ⚠️ Disclaimer

This project uses anonymized and simulated data for demonstration purposes.
