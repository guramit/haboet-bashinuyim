-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone TEXT UNIQUE NOT NULL,
    name TEXT,
    business_name TEXT,
    business_field TEXT,
    main_challenges TEXT[],
    focus_areas TEXT[],
    daily_commitment INTEGER DEFAULT 30,
    timezone TEXT DEFAULT 'Asia/Jerusalem',
    is_active BOOLEAN DEFAULT true,
    streak_days INTEGER DEFAULT 0,
    onboarding_step TEXT DEFAULT 'name',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily Plans table
CREATE TABLE daily_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    plan_date DATE NOT NULL,
    day_type TEXT DEFAULT 'regular',
    morning_message TEXT,
    completion_rate FLOAT DEFAULT 0,
    mood_score INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plan_date)
);

-- Tasks table
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    daily_plan_id UUID REFERENCES daily_plans(id),
    user_id UUID REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    status TEXT DEFAULT 'pending',
    difficulty_actual INTEGER,
    user_notes TEXT,
    order_num INTEGER,
    is_carryover BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Task Library (pre-populated)
CREATE TABLE task_library (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    difficulty_level INTEGER CHECK (difficulty_level BETWEEN 1 AND 5),
    time_estimate_minutes INTEGER,
    tags TEXT[],
    business_fields TEXT[]
);

-- Interactions (conversation history)
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    intent_detected TEXT,
    sentiment_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Patterns (AI insights)
CREATE TABLE user_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    pattern_type TEXT,
    description TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    action_taken TEXT
);

-- Indexes for performance
CREATE INDEX idx_daily_plans_user_date ON daily_plans(user_id, plan_date);
CREATE INDEX idx_tasks_plan ON tasks(daily_plan_id);
CREATE INDEX idx_interactions_user ON interactions(user_id, created_at DESC);
