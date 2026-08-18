AI Marketing Automation Platform — Product Development Plan

Hello Shreyas and Digvijay
to run this project

# terminal 1
cd backend; venv\Scripts\Activate.ps1; 
python manage.py runserver
# terminal 2
cd frontend; npm run dev



1. Product Overview

Product

AI Digital Marketing Automation SaaS Platform

Goal

Build a multi-tenant SaaS platform that helps businesses automate their digital marketing workflow:

Admin creates and manages client companies.

Admin stores complete business and brand information.

Client login is created and provided by Admin.

WhatsApp collaboration/notification workflow is connected.

Admin uploads or manages a monthly content calendar, including Excel import.

AI automatically generates social media creatives and videos.

Client reviews generated content.

Client can approve or reject content.

Rejection allows feedback and one regeneration.

Approved content can be published to Instagram, Facebook and LinkedIn.

System collects analytics and generates reports.

Subscriptions are managed manually by Admin; there is no online subscription purchase flow.

2. Business Model

SaaS Model

The product is sold to businesses as a monthly SaaS service.

Important Scope Decision

Subscription purchase functionality is not part of the application.

Admin will manually:

Create subscription

Assign plan

Set start date

Set expiry date

Set usage limits

Track usage

Update subscription status

Record billing/payment information manually

The system will NOT include:

Online checkout

Payment gateway

Automatic subscription purchase

Customer self-service plan purchase

3. User Roles

Only two application roles are required.

3.1 Admin

Admin is the internal platform/team user.

Responsibilities:

Company management

Client management

Brand management

Content calendar

AI settings

AI generation monitoring

Approval monitoring

Social account management

WhatsApp management

Publishing monitoring

Analytics

Reports

Manual subscription management

Usage monitoring

Support

System settings

Activity/audit monitoring

3.2 Client

Client is the business/customer user.

Capabilities:

Login

View dashboard

View company/brand information

View content calendar

Preview creatives

Preview videos

Approve content

Reject content

Give feedback

Use one-time regeneration

View publishing status

View published content

View analytics

View reports

Manage profile/settings

4. Core Business Workflow

Admin
  ↓
Create Company
  ↓
Add Business Details
  ↓
Add Brand Information
  ↓
Create Client Login
  ↓
Configure WhatsApp
  ↓
Connect Social Accounts
  ↓
Upload/Create Content Calendar
  ↓
Scheduler
  ↓
AI Content Generation
  ↓
Generate 3 Creative Samples / Video
  ↓
Client Review
  ↓
 ┌───────────────────────┐
 │                       │
Approve                Reject
 │                       │
 ↓                       ↓
Publish              Feedback
                         ↓
                   Regenerate Once
                         ↓
                    Client Review
                         ↓
                       Approve
                         ↓
                      Publish
                         ↓
                 Analytics Collection
                         ↓
                    Monthly Report

5. Recommended Technology Stack

Frontend

React

TypeScript

Vite

Tailwind CSS

shadcn/ui

React Router

Axios

Backend

Recommended Framework: Django

Use:

Python

Django

Django REST Framework

PostgreSQL

Celery

Redis

Why Django?

Django is recommended because the product requires:

Strong authentication

Admin/business management

ORM

Complex relational database

Multi-tenant business data

Background jobs

API development

Security

Mature ecosystem

Fast development with a two-person team

FastAPI is excellent for high-performance API and AI microservices, but for this product Django provides a stronger all-in-one foundation. A separate FastAPI AI service can be introduced later if required.

Database

PostgreSQL

Queue / Background Processing

Redis

Celery

Storage

AWS S3 or Cloudflare R2

Media Processing

FFmpeg

AI Layer

Provider-agnostic architecture supporting:

Text/LLM provider

Image generation provider

Video generation provider

The exact providers should be selected after API, quality, cost and commercial-use evaluation.

External Integrations

Instagram / Meta APIs

Facebook Graph API

LinkedIn APIs

WhatsApp Business API

Email provider

Social analytics APIs

DevOps

Docker

GitHub

GitHub Actions

Nginx

SSL

Cloud/server infrastructure

Monitoring and logging

6. Software Development Methodology

Agile Methodology

The product will be developed using Agile.

Development Approach

Product backlog

Epics

User stories

Tasks

Sprint planning

Daily stand-up

Development

Code review

Testing

Sprint review

Retrospective

Backlog refinement

Sprint Duration

Recommended:

1 week per sprint

3 hours/day/developer

Team

Shreyas

Digvijay

Approximate team capacity:

2 developers × 3 hours/day
≈ 6 developer-hours/day
≈ 30 developer-hours/week

7. Master Product Backlog

Epic 01 — Authentication & User Management

Authentication

Login

Logout

JWT authentication

Access token

Refresh token

Forgot password

Reset password

Change password

Session expiry

User Management

Create client user

Edit user

Activate/deactivate user

User profile

Password management

Login history

Role & Access

Admin role

Client role

Permissions

Protected routes

API authorization

8. Epic 02 — Company / Customer Management

Company Management

Add company

Edit company

View company

Deactivate company

Company status

Company details

Business Information

Company name

Industry

Business description

Website

Contact details

Address

Target market

Target audience

Products

Services

USP

Competitors

Client Management

Create client

Assign client to company

Create login

Client status

Client access

Onboarding

Onboarding checklist

Required information

Completion status

9. Epic 03 — Brand Management

Brand Identity

Logo

Secondary logo

Favicon

Brand colors

Color palette

Fonts

Typography

Brand Guidelines

Brand voice

Tone

Writing style

Visual style

Do's and don'ts

Keywords

Restricted words

Marketing Information

Target audience

Customer personas

Products

Services

USP

Competitors

Offers

Campaign information

Brand Assets

Logo uploads

Reference images

Product images

Documents

Marketing materials

10. Epic 04 — Content Calendar

Calendar Management

Create calendar

Monthly calendar

Weekly calendar

Daily content

Edit calendar

Delete calendar

Duplicate calendar

Content Planning

Content topic

Category

Objective

Campaign

Platform

Content type

Date

Time

Caption requirements

Creative requirements

CTA

Hashtags

Content Types

Single image

Carousel

Grid

Story

Reel

Short video

Promotional

Educational

Festival

Product

Announcement

Testimonial

Excel

Excel template

Excel upload

Validation

Import preview

Import

Invalid row detection

Error report

Status

Draft

Scheduled

Generating

Generated

Pending approval

Approved

Rejected

Published

Failed

11. Epic 05 — AI Content Strategy

AI Planning

Content ideas

Topic suggestions

Content themes

Campaign suggestions

Posting suggestions

Brand Understanding

Analyze business

Analyze brand guidelines

Analyze products/services

Analyze audience

Create brand context

AI Strategy

Content strategy

Platform strategy

Audience strategy

Campaign strategy

12. Epic 06 — AI Creative Generation

Image Generation

Instagram post

Facebook post

LinkedIn post

Carousel

Story

Promotional creative

Festival creative

Product creative

Variations

Generate 3 samples

Variation 1

Variation 2

Variation 3

Select preferred version

Copy

Caption

Headline

Description

CTA

Hashtags

Keywords

Brand-Aware Generation

Brand colors

Logo

Brand tone

Typography

Visual style

Product information

Generation Management

Generation request

Queue

Status

Success

Failure

Retry

Usage tracking

Cost tracking

13. Epic 07 — AI Video Generation

Video Creation

Instagram Reel

Facebook Reel

LinkedIn video

Short video

Promotional video

Product video

Educational video

Components

Script

Scenes

Images

AI visuals

Voice-over

Music

Subtitles

Logo

Brand colors

Processing

Rendering

FFmpeg

Aspect ratio

Resolution

Duration

Compression

Thumbnail

Management

Queue

Status

Failed generation

Retry

Storage

Preview

14. Epic 08 — Media Management

Media Library

Images

Videos

Logos

Documents

Generated content

Uploaded content

File Management

Upload

Download

Delete

Preview

Rename

Metadata

Storage

S3/R2

CDN

Storage limits

File validation

File size limits

File type validation

15. Epic 09 — Content Approval Workflow

Approval

Pending approval

View creative

View video

Approve

Reject

Rejection

Rejection reason

Feedback

Change request

Instructions

Regeneration

Regenerate

Apply feedback

One-time regeneration

Regeneration status

Regenerated content

History

Approval history

Rejection history

Feedback history

Regeneration history

User activity

16. Epic 10 — Social Media Account Management

Instagram

Connect

OAuth

Account information

Status

Disconnect

Token management

Facebook

Connect

Page selection

OAuth

Status

Disconnect

Token management

LinkedIn

Connect

Organization selection

OAuth

Status

Disconnect

Token management

Security

Token encryption

Token expiry

Token refresh

Permissions

Connection errors

17. Epic 11 — Publishing & Scheduling

Publishing

Publish now

Publish approved content

Platform selection

Multi-platform publishing

Scheduling

Schedule post

Schedule reel

Date/time

Timezone

Publishing queue

Status

Scheduled

Processing

Published

Failed

Retry

Cancel

History

Published content

Platform

Date

Status

Error logs

18. Epic 12 — WhatsApp Automation

Configuration

WhatsApp API

Business number

Internal numbers

Client number

Group

Create group

Add client

Add internal numbers

Group status

Group information

Notifications

Content generated

Approval required

Approved

Rejected

Regenerated

Published

Publishing failed

Reminder

Templates

Approval template

Reminder template

Publishing template

Monthly report template

19. Epic 13 — Notification Center

In-App

Notification list

Read/unread

Mark as read

Notification history

Email

Welcome

Login information

Approval

Publishing

Report

Password reset

WhatsApp

Approval

Reminder

Publishing

Reports

20. Epic 14 — Dashboard

Admin Dashboard

Total companies

Active clients

Content generated

Pending approvals

Published posts

Failed posts

AI usage

Subscription status

Client Dashboard

Upcoming content

Pending approvals

Approved content

Published content

Performance summary

Notifications

Widgets

Content statistics

Approval statistics

Publishing statistics

AI usage

Engagement

Calendar summary

21. Epic 15 — Analytics

Instagram

Reach

Impressions

Views

Likes

Comments

Shares

Saves

Followers

Facebook

Reach

Impressions

Engagement

Likes

Comments

Shares

Followers

LinkedIn

Impressions

Reactions

Comments

Shares

Clicks

Followers

Performance

Engagement rate

Top posts

Best content type

Best platform

Growth

Campaign performance

Synchronization

Fetch analytics

Scheduled sync

API failure handling

Retry

Historical data

22. Epic 16 — Reports

Client Reports

Monthly report

Content report

Publishing report

Engagement report

Growth report

Admin Reports

Company report

Client report

AI usage report

Approval report

Publishing report

Subscription report

Export

PDF

Excel

CSV

Automation

Monthly report generation

Email report

WhatsApp report

Download report

23. Epic 17 — Subscription & Usage Management

Subscription

Create subscription

Assign plan

Edit

Start date

End date

Status

Renewal date

Expiry

Plans

Plan name

Price

Creative limit

Video limit

Publishing limit

Storage limit

Platform limits

Usage

Creative usage

Video usage

Publishing usage

Storage usage

Usage percentage

Usage limits

Manual Billing

Billing information

Invoice information

Payment status

Payment reference

Billing history

24. Epic 18 — Activity & Audit Logs

User Activity

Login

Logout

Company creation

Company update

Calendar update

Generation

Approval

Rejection

Publishing

Admin Activity

Client creation

Subscription update

Social connection

Settings changes

Audit

User

Action

Timestamp

IP

Module

Old value

New value

25. Epic 19 — Admin Settings

AI provider settings

Model settings

Prompt settings

Generation limits

Notification settings

Publishing settings

Timezone

Language

File limits

Storage settings

26. Epic 20 — Client Settings

Profile

Name

Email

Phone

Profile image

Security

Change password

Login sessions

Notifications

Email preferences

WhatsApp preferences

Dashboard notifications

27. Epic 21 — AI Prompt & Template Management

Prompt Library

Caption prompts

Image prompts

Video prompts

Hashtag prompts

Campaign prompts

Templates

Instagram

Facebook

LinkedIn

Reel

Carousel

Festival

Product

Versioning

Create version

Update version

Activate/deactivate

History

28. Epic 22 — Automation Engine

Content Automation

Calendar
 ↓
Scheduler
 ↓
AI Generation
 ↓
Storage
 ↓
Approval

Approval Automation

Generated
 ↓
Notify Client
 ↓
Wait
 ↓
Approve/Reject

Regeneration

Reject
 ↓
Feedback
 ↓
AI Regeneration
 ↓
Review

Publishing

Approved
 ↓
Publishing Queue
 ↓
Social Platform
 ↓
Status

Analytics

Published
 ↓
Analytics Fetch
 ↓
Store Data
 ↓
Generate Report

29. Epic 23 — Background Jobs & Queue Management

Celery Jobs

AI generation

Video generation

Publishing

Analytics

Notifications

Reports

Job Status

Pending

Processing

Completed

Failed

Retry

Cancel

Scheduler

Daily jobs

Scheduled publishing

Analytics sync

Report generation

Reminders

30. Epic 24 — Security

Application

JWT security

Password hashing

API permissions

CORS

CSRF

Rate limiting

Data

Sensitive data encryption

Social token encryption

Secure file storage

Database security

Access

Admin isolation

Client isolation

Company data isolation

API authorization

Monitoring

Security logs

Login monitoring

Suspicious activity

31. Epic 25 — Multi-Tenant SaaS Architecture

Tenant Management

Company as tenant

Tenant ID

Tenant isolation

Data Isolation

Company A
 ├── Users
 ├── Calendar
 ├── Content
 ├── Social Accounts
 └── Analytics

Company B
 ├── Users
 ├── Calendar
 ├── Content
 ├── Social Accounts
 └── Analytics

Company A must never access Company B's data.

Tenant Configuration

Brand settings

AI settings

Subscription limits

Social accounts

Notification settings

32. Epic 26 — DevOps & Infrastructure

Development

Local environment

Environment variables

Docker

Docker Compose

CI/CD

GitHub

Branching strategy

Pull requests

Automated tests

Build

Deployment

Production

Backend

Frontend

PostgreSQL

Redis

Celery

Nginx

SSL

Monitoring

Application logs

Error tracking

Server monitoring

Celery monitoring

Database monitoring

Backup

Database backup

Media backup

Disaster recovery

33. Epic 27 — Testing & QA

Backend

Unit tests

API tests

Authentication tests

Permission tests

Service tests

Frontend

Component tests

Form tests

Navigation tests

Responsive tests

Integration

AI

Social APIs

WhatsApp

Storage

Celery

End-to-End

Complete workflow testing:

Admin
 ↓
Company
 ↓
Client
 ↓
Brand
 ↓
Calendar
 ↓
AI Generation
 ↓
Client Review
 ↓
Approve/Reject
 ↓
Regeneration
 ↓
Approve
 ↓
Publish
 ↓
Analytics
 ↓
Report

34. Epic 28 — Documentation

Product

PRD

SRS

Design document

Architecture document

Technical

API documentation

Database documentation

Deployment documentation

Environment setup

User

Admin guide

Client guide

FAQ

Troubleshooting

35. Sprint Plan

Because the team has only two developers and 3 hours/day each, the complete platform should be treated as a roadmap. The first release should focus on the core workflow.

Sprint 0 — Planning & Foundation

Goals

Finalize requirements

Finalize architecture

Git repository

Development standards

Environment setup

Database setup

Frontend setup

Backend setup

CI baseline

Output

Working development environment.

Sprint 1 — Authentication + Company

Modules

Authentication

User management

Company management

Client management

Output

Admin can create a company and client login.

Sprint 2 — Branding + Dashboard

Modules

Brand management

Admin dashboard

Client dashboard

Settings foundation

Output

Company has complete brand profile and both portals work.

Sprint 3 — Content Calendar

Modules

Content calendar

Excel import

Calendar validation

Content status

Output

Admin can upload monthly Excel calendar and manage content.

Sprint 4 — AI Creative Generation

Modules

AI strategy

AI creative generation

Prompt system

AI queue

Media management

Output

System generates 3 creative variations.

Sprint 5 — Approval Workflow

Modules

Approval

Rejection

Feedback

One-time regeneration

Notifications

Output

Client can review, approve, reject and regenerate once.

Sprint 6 — Social Accounts + Publishing

Modules

Instagram

Facebook

LinkedIn

OAuth

Publishing

Scheduling

Output

Approved content can be published/scheduled.

Sprint 7 — AI Video + WhatsApp

Modules

AI video

Video processing

WhatsApp

Notification automation

Output

System can generate video content and notify users.

Sprint 8 — Analytics + Reports

Modules

Analytics

Reports

PDF/Excel export

Output

Client can see performance and monthly reports.

Sprint 9 — Subscription + SaaS

Modules

Manual subscriptions

Usage

Limits

Tenant management

Audit logs

Output

Admin can manage client plans and usage.

Sprint 10 — QA + Production

Modules

Testing

Security

DevOps

Monitoring

Backup

Documentation

Output

Production-ready release.

36. Two-Developer Module Assignment

The backlog should be assigned by module ownership rather than simply separating frontend and backend.

Shreyas — Suggested Ownership

Authentication & User Management

Company / Customer Management

Brand Management

AI Content Strategy

AI Creative Generation

AI Video Generation

Media Management

Publishing & Scheduling

Analytics

Security

DevOps & Infrastructure

Background Jobs / Queue

Digvijay — Suggested Ownership

Dashboard

Content Calendar

Approval Workflow

Social Media Account Management

WhatsApp Automation

Notification Center

Reports

Subscription & Usage Management

Activity & Audit Logs

Admin Settings

Client Settings

AI Prompt & Template Management

Multi-Tenant UI/Workflow

Shared

Both developers:

Architecture decisions

Database reviews

API contract reviews

Code reviews

Testing

Bug fixing

Sprint planning

Sprint review

Retrospective

Production support

Ownership means the developer is responsible for the module's completion and coordination. It does not prevent the other developer from contributing code.

37. Agile Workflow

Product Backlog

Epic
 ↓
Feature
 ↓
User Story
 ↓
Task
 ↓
Subtask

Example:

Epic: AI Creative Generation

Feature: Instagram Creative

User Story:
As an admin, I want the system to generate
Instagram creatives from the content calendar.

Tasks:
- Create AI request model
- Create prompt service
- Integrate AI provider
- Create generation queue
- Store generated media
- Create preview UI
- Add generation status
- Test generation

38. Git Branching Strategy

Recommended:

main
 │
 ├── develop
 │
 ├── feature/authentication
 ├── feature/company-management
 ├── feature/content-calendar
 ├── feature/ai-generation
 ├── feature/approval
 └── feature/publishing

Developers should:

Create feature branch.

Implement feature.

Test locally.

Push branch.

Create Pull Request.

Review.

Merge into develop.

Test integration.

Release stable version to main.

39. Definition of Ready

A story is ready when:

Requirement is clear.

Acceptance criteria exist.

UI/UX is available or defined.

API/data requirements are understood.

Dependencies are identified.

Developer can estimate the task.

40. Definition of Done

A feature is Done only when:

Code is complete.

API/UI is integrated.

Validation exists.

Error handling exists.

Tests pass.

No critical bugs exist.

Code is reviewed.

Documentation is updated where required.

Feature is deployed to the testing environment.

41. MVP Priority

P0 — Core Product

Must have:

Authentication

Company management

Client management

Brand management

Content calendar

Excel import

AI creative generation

Media management

Approval workflow

Social account connection

Publishing

Basic dashboard

P1 — Automation

AI video generation

WhatsApp automation

Notification center

Prompt management

Background jobs

Scheduling

P2 — Business Intelligence

Analytics

Reports

Manual subscription

Usage management

Audit logs

P3 — Scale & Production

Multi-tenant hardening

Security hardening

DevOps

Monitoring

Backup

Advanced testing

Documentation

42. Core MVP Release Flow

The first commercially useful version should successfully complete this flow:

Admin Login
     ↓
Create Company
     ↓
Add Client
     ↓
Add Brand Information
     ↓
Client Login
     ↓
Upload Monthly Excel Calendar
     ↓
System Creates Content Calendar
     ↓
Scheduler Detects Content
     ↓
AI Generates 3 Creative Options
     ↓
Client Receives Notification
     ↓
Client Reviews
     ↓
Approve
     ↓
Publish to Social Media
     ↓
Publishing Status

Rejection flow:

Client Rejects
     ↓
Feedback
     ↓
AI Regenerates Once
     ↓
Client Reviews Again
     ↓
Approve
     ↓
Publish

43. Long-Term Product Architecture

                    CLIENT / ADMIN
                          │
                          ▼
                    React Frontend
                          │
                          ▼
                    Django REST API
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
       ▼                  ▼                  ▼
 Company Service     Content Service     User Service
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                          ▼
                  Automation Engine
                          │
                  ┌───────┴───────┐
                  ▼               ▼
               Redis            Celery
                  │               │
                  └───────┬───────┘
                          ▼
                    AI Services
             ┌────────────┼────────────┐
             ▼            ▼            ▼
           Text         Image        Video
             │            │            │
             └────────────┼────────────┘
                          ▼
                     Media Storage
                       S3 / R2
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         Instagram     Facebook     LinkedIn
                          │
                          ▼
                      Analytics
                          │
                          ▼
                       Reports

44. Important Product Principles

Build multi-tenant architecture from the beginning.

Keep AI providers replaceable.

Never store social access tokens as plain text.

Use background jobs for AI, video, publishing and analytics.

Never make AI generation synchronous for long-running jobs.

Keep media outside PostgreSQL; store media in object storage.

Every company must have strict data isolation.

Every important action should be auditable.

Design for retries because external APIs and AI providers can fail.

Track AI usage and cost.

Keep subscription purchase out of scope; subscriptions are manually managed.

Use API versioning such as /api/v1/.

Use automated tests before production deployment.

Keep development, staging and production environments separate.

Build the MVP workflow before advanced features.

45. One-Month Execution Strategy

With 2 developers working approximately 3 hours/day, prioritize the core workflow.

Week 1

Project foundation

Authentication

Company

Client

Branding

Basic dashboards

Week 2

Content calendar

Excel import

AI creative generation

Media management

Week 3

Approval workflow

Regeneration

Social account connection

Publishing

Week 4

Basic video generation

Notifications

Basic analytics

Manual subscription

Testing

Deployment

Advanced analytics, sophisticated video generation, complete WhatsApp automation, advanced reporting, extensive security hardening and scale optimization should continue after the initial MVP if they cannot be completed reliably within the available capacity.

46. Final Product Goal

The finished platform should evolve into an AI-powered marketing operating system where:

Business Data
      ↓
Brand Intelligence
      ↓
Content Strategy
      ↓
Content Calendar
      ↓
AI Creative + Video Generation
      ↓
Client Approval
      ↓
Automated Publishing
      ↓
Analytics
      ↓
Reports
      ↓
Continuous Content Optimization

The key product objective is not merely to generate AI images. The platform should automate the complete marketing content lifecycle from planning to generation, approval, publishing and measurement.