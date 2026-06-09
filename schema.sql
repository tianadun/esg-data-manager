DROP TABLE IF EXISTS emissions;
DROP TABLE IF EXISTS datapoints;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    company_name TEXT NOT NULL
);

CREATE TABLE datapoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reporting_year INTEGER NOT NULL,
    reporting_period TEXT NOT NULL,
    esrs_area TEXT NOT NULL,
    topic TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL,
    unit TEXT,
    department TEXT NOT NULL,
    data_source TEXT,
    evidence_link TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE emissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reporting_year INTEGER NOT NULL,
    reporting_period TEXT NOT NULL,
    scope TEXT NOT NULL,
    emissions_category TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    activity_value REAL NOT NULL,
    activity_unit TEXT NOT NULL,
    emission_factor REAL NOT NULL,
    emission_factor_unit TEXT NOT NULL,
    emission_factor_source TEXT,
    calculated_emissions_kg REAL NOT NULL,
    department TEXT NOT NULL,
    data_source TEXT,
    evidence_link TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

