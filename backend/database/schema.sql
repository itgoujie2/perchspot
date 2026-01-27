-- Housing Analysis Database Schema
-- MySQL 8.0+

-- Properties table - core property information
CREATE TABLE IF NOT EXISTS properties (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    address TEXT NOT NULL,
    address_normalized TEXT NOT NULL,
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Property details
    price DECIMAL(12, 2),
    bedrooms INTEGER,
    bathrooms DECIMAL(3, 1),
    square_feet INTEGER,
    lot_size INTEGER,
    year_built INTEGER,
    property_type VARCHAR(50),
    description TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_address (address_normalized(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_properties_location ON properties(latitude, longitude);
CREATE INDEX idx_properties_zip ON properties(zip_code);
CREATE INDEX idx_properties_created ON properties(created_at DESC);

-- Property data sources - raw data from external APIs
CREATE TABLE IF NOT EXISTS property_data_sources (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    property_id CHAR(36),
    source VARCHAR(50) NOT NULL,
    data JSON NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY unique_property_source (property_id, source),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_property_sources ON property_data_sources(property_id, source);
CREATE INDEX idx_sources_fetched ON property_data_sources(fetched_at DESC);

-- Property images
CREATE TABLE IF NOT EXISTS property_images (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    property_id CHAR(36),
    image_url TEXT,
    storage_path TEXT,
    image_type VARCHAR(50),
    caption TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_property_images ON property_images(property_id);
CREATE INDEX idx_image_type ON property_images(image_type);

-- Schools table
CREATE TABLE IF NOT EXISTS schools (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(200) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    school_type VARCHAR(50),
    rating DECIMAL(3, 1),
    data JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_school (name, address(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_schools_location ON schools(latitude, longitude);
CREATE INDEX idx_schools_type ON schools(school_type);
CREATE INDEX idx_schools_rating ON schools(rating DESC);

-- Property-School relationship
CREATE TABLE IF NOT EXISTS property_schools (
    property_id CHAR(36),
    school_id CHAR(36),
    distance_miles DECIMAL(5, 2),

    PRIMARY KEY (property_id, school_id),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_property_schools_distance ON property_schools(distance_miles);

-- Property analyses - main analysis results
CREATE TABLE IF NOT EXISTS property_analyses (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    property_id CHAR(36),

    -- Overall scores
    overall_score DECIMAL(5, 2) NOT NULL,
    overall_grade VARCHAR(2) NOT NULL,
    confidence_level VARCHAR(20) NOT NULL,

    -- Category scores
    property_condition_score DECIMAL(5, 2),
    location_quality_score DECIMAL(5, 2),
    schools_score DECIMAL(5, 2),
    investment_value_score DECIMAL(5, 2),

    -- Detailed analysis results (JSON)
    condition_analysis JSON,
    location_analysis JSON,
    school_analysis JSON,
    investment_analysis JSON,

    -- Metadata
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    llm_model VARCHAR(50),
    llm_cost DECIMAL(10, 4),
    processing_time_seconds INTEGER,

    UNIQUE KEY unique_property_analysis (property_id, analyzed_at),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_analyses_property ON property_analyses(property_id);
CREATE INDEX idx_analyses_score ON property_analyses(overall_score DESC);
CREATE INDEX idx_analyses_date ON property_analyses(analyzed_at DESC);

-- Analysis reports - generated reports (PDF, HTML)
CREATE TABLE IF NOT EXISTS analysis_reports (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    analysis_id CHAR(36),
    pdf_path TEXT,
    html_content MEDIUMTEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY unique_analysis_report (analysis_id),
    FOREIGN KEY (analysis_id) REFERENCES property_analyses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_reports_analysis ON analysis_reports(analysis_id);

-- API usage logs - track API costs and usage
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    service VARCHAR(50) NOT NULL,
    endpoint VARCHAR(100),
    request_params JSON,
    tokens_used INTEGER,
    cost DECIMAL(10, 4),
    response_time_ms INTEGER,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_usage_service ON api_usage_logs(service, logged_at DESC);
CREATE INDEX idx_usage_status ON api_usage_logs(status);
CREATE INDEX idx_usage_date ON api_usage_logs(logged_at DESC);

-- API cache - cache external API responses
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key VARCHAR(255) PRIMARY KEY,
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_cache_expiry ON api_cache(expires_at);

-- Analysis jobs - track async analysis jobs
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    property_id CHAR(36),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    current_step VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_jobs_status ON analysis_jobs(status);
CREATE INDEX idx_jobs_created ON analysis_jobs(created_at DESC);
CREATE INDEX idx_jobs_property ON analysis_jobs(property_id);

-- Comparable properties - for investment analysis
CREATE TABLE IF NOT EXISTS comparable_properties (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    property_id CHAR(36),
    comparable_address TEXT NOT NULL,
    distance_miles DECIMAL(5, 2),
    price DECIMAL(12, 2),
    square_feet INTEGER,
    price_per_sqft DECIMAL(10, 2),
    bedrooms INTEGER,
    bathrooms DECIMAL(3, 1),
    sale_date DATE,
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_comparables_property ON comparable_properties(property_id);
CREATE INDEX idx_comparables_distance ON comparable_properties(distance_miles);

-- View for recent analyses with property details
CREATE OR REPLACE VIEW recent_analyses AS
SELECT
    pa.id AS analysis_id,
    pa.overall_score,
    pa.overall_grade,
    pa.confidence_level,
    pa.analyzed_at,
    p.address,
    p.city,
    p.state,
    p.price,
    p.bedrooms,
    p.bathrooms,
    p.square_feet
FROM property_analyses pa
JOIN properties p ON pa.property_id = p.id
ORDER BY pa.analyzed_at DESC;

-- View for API cost summary
CREATE OR REPLACE VIEW api_cost_summary AS
SELECT
    service,
    DATE(logged_at) AS date,
    COUNT(*) AS request_count,
    SUM(cost) AS total_cost,
    AVG(response_time_ms) AS avg_response_time,
    COUNT(CASE WHEN status = 'error' THEN 1 END) AS error_count
FROM api_usage_logs
GROUP BY service, DATE(logged_at)
ORDER BY date DESC, service;
