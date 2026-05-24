-- ============================================
-- AgentSaaS Database Schema
-- Run this in Supabase SQL Editor
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. PROFILES (extends Supabase auth.users)
-- ============================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, avatar_url)
    VALUES (NEW.id, NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'avatar_url');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- ============================================
-- 2. ORGANIZATIONS
-- ============================================
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    subscription_plan TEXT DEFAULT 'starter', -- starter, pro, enterprise
    subscription_status TEXT DEFAULT 'active', -- active, past_due, cancelled
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- 3. ORGANIZATION MEMBERS
-- ============================================
CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member', -- owner, admin, member
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, organization_id)
);

-- ============================================
-- 4. AGENTS (config-driven, stored in DB)
-- ============================================
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    model TEXT DEFAULT 'gpt-4o-mini',
    temperature FLOAT DEFAULT 0.7,
    enabled_tools JSONB DEFAULT '[]',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- 5. CONVERSATIONS
-- ============================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'New Conversation',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON conversations(organization_id);
INDEX ON conversations(user_id);
INDEX ON conversations(agent_id);

-- ============================================
-- 6. MESSAGES
-- ============================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON messages(conversation_id);
INDEX ON messages(organization_id);

-- ============================================
-- 7. DOCUMENTS
-- ============================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT,
    extracted_text TEXT,
    storage_path TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON documents(organization_id);

-- ============================================
-- 8. AGENT RUNS (logging/observability)
-- ============================================
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    input_prompt TEXT,
    output TEXT,
    status TEXT DEFAULT 'running', -- running, completed, failed
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON agent_runs(organization_id);
INDEX ON agent_runs(agent_id);

-- ============================================
-- 9. TOKEN USAGE (profitability tracking)
-- ============================================
CREATE TABLE token_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    estimated_cost FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON token_usage(organization_id);
INDEX ON token_usage(created_at);

-- ============================================
-- 10. TOOL LOGS (observability)
-- ============================================
CREATE TABLE tool_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    input_data JSONB,
    output_data JSONB,
    status TEXT DEFAULT 'success', -- success, failed
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON tool_logs(organization_id);

-- ============================================
-- 11. PROMPT VERSIONS (versioning system)
-- ============================================
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT false,
    notes TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(agent_id, version)
);

INDEX ON prompt_versions(agent_id);

-- ============================================
-- 12. CONVERSATION MEMORY (summaries)
-- ============================================
CREATE TABLE conversation_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    message_range_start INTEGER,
    message_range_end INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

INDEX ON conversation_memory(conversation_id);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompt_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_memory ENABLE ROW LEVEL SECURITY;

-- Profiles: users can only see their own profile
CREATE POLICY "Users can view own profile"
    ON profiles FOR SELECT
    USING (auth.uid() = id);

-- Agents: everyone can read (public catalog)
CREATE POLICY "Anyone can view agents"
    ON agents FOR SELECT
    USING (true);

-- Organizations: members can view
CREATE POLICY "Members can view organizations"
    ON organizations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = organizations.id
            AND organization_members.user_id = auth.uid()
        )
    );

CREATE POLICY "Members can insert organizations"
    ON organizations FOR INSERT
    WITH CHECK (true);

-- Organization members: can view own memberships
CREATE POLICY "Users can view own memberships"
    ON organization_members FOR SELECT
    USING (user_id = auth.uid());

-- Conversations: org members can access
CREATE POLICY "Members can view conversations"
    ON conversations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = conversations.organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

CREATE POLICY "Members can create conversations"
    ON conversations FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

-- Messages: org members can access
CREATE POLICY "Members can view messages"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = messages.organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

CREATE POLICY "Members can create messages"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

-- Documents: org members can access
CREATE POLICY "Members can view documents"
    ON documents FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = documents.organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

-- Agent runs: org members can view
CREATE POLICY "Members can view agent runs"
    ON agent_runs FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = agent_runs.organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

-- Token usage: org members can view
CREATE POLICY "Members can view token usage"
    ON token_usage FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = token_usage.organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

-- Conversation memory: org members can access
CREATE POLICY "Members can view conversation memory"
    ON conversation_memory FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_members.organization_id = conversation_memory.organization_id
            AND organization_members.user_id = auth.uid()
        )
    );

-- ============================================
-- SEED DATA: Initial Agents
-- ============================================

INSERT INTO agents (name, slug, description, system_prompt, model, temperature, enabled_tools) VALUES
(
    'Marketing Agent',
    'marketing',
    'Creates marketing campaigns, ad copy, content calendars, and competitor analysis',
    'You are an expert marketing AI assistant. Help businesses create effective marketing campaigns, write compelling ad copy, plan content calendars, and analyze competitors. Always provide actionable, data-driven advice. Support both Arabic and English content.',
    'gpt-4o-mini',
    0.7,
    '["web_search", "competitor_analyzer", "ad_copy_generator", "landing_page_analyzer"]'
),
(
    'Sales Agent',
    'sales',
    'Manages leads, generates proposals, creates follow-ups, and closes deals',
    'You are an expert sales AI assistant. Help businesses manage their sales pipeline, write proposals, create follow-up messages, and close deals. Be persuasive but professional. Support both Arabic and English communication.',
    'gpt-4o-mini',
    0.7,
    '["crm_lead_saver", "follow_up_generator", "proposal_generator", "whatsapp_sender"]'
),
(
    'SEO Agent',
    'seo',
    'Optimizes content for search engines, analyzes keywords, and improves rankings',
    'You are an expert SEO AI assistant. Help businesses optimize their content for search engines, research keywords, analyze competitors, and improve their search rankings. Provide specific, actionable SEO recommendations.',
    'gpt-4o-mini',
    0.7,
    '["web_search", "keyword_research", "content_optimizer", "technical_audit"]'
),
(
    'Customer Support Agent',
    'support',
    'Handles customer inquiries, creates responses, and manages support tickets',
    'You are an expert customer support AI assistant. Help businesses respond to customer inquiries professionally and efficiently. Be empathetic, clear, and solution-oriented. Support both Arabic and English communication.',
    'gpt-4o-mini',
    0.5,
    '["knowledge_base_search", "ticket_classifier", "response_generator"]'
);
