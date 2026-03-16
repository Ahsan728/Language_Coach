# Language Coach Android Project Workflow

## Purpose

This document converts the current Language Coach web application into an execution-ready, phase-by-phase workflow for building a native Android application without disrupting the live web product.

Companion UI specification: `docs/android_ui_screen_spec.md`

The plan assumes the current system remains the source of truth during migration:

- Flask backend in `app.py`
- Server-rendered HTML templates
- Browser-side logic in `static/js/app.js`
- JSON content in `data/lessons.json` and `data/vocabulary.json`
- SQLite progress and feedback storage in `data/progress.db`

The target outcome is a production Android app that reuses the existing learning content and core business rules while moving mobile delivery away from HTML pages and browser-only APIs.

## Recommended Agent Roles

Assign separate agents or teams to these roles:

| Role | Primary Responsibility |
| --- | --- |
| Product and Architecture Agent | Scope, phase sequencing, acceptance criteria, dependency control |
| Backend API Agent | Flask modularization, JSON API design, auth/session strategy, data contracts |
| Android Foundation Agent | App shell, navigation, dependency injection, networking, persistence |
| Android Learning Features Agent | Lessons, vocabulary, quizzes, practice, flashcards, progress UX |
| Speech and Media Agent | TTS playback, dictation, speech recognition, permissions, audio UX |
| Content and Data Agent | JSON validation, lesson mapping, vocabulary consistency, migration support |
| QA and Release Agent | Test plan, regression checks, release readiness, Play Store packaging |
| UI and Design Agent | Mobile design system, interaction polish, empty states, accessibility |

## Delivery Rules

Use these rules across all phases:

1. Keep the existing web app deployable at all times.
2. Do not break the current live user flows while extracting APIs.
3. Treat content JSON as a stable contract until a new content pipeline is approved.
4. Build Android against explicit API contracts, not scraped HTML.
5. Ship read-only content flows before speech-heavy and offline-heavy features.
6. Gate each phase with testable acceptance criteria.
7. Log blockers and assumptions in writing at each handoff.

## Current-State Constraints

The Android plan must respect the current technical realities:

- The backend is monolithic. Most application logic lives in `app.py`.
- Auth is email-only and session-cookie based.
- Mobile-relevant APIs are incomplete. Current JSON APIs cover only TTS, translate, feedback, lesson completion, and word progress.
- Speaking and dictation currently rely on browser speech APIs in `static/js/app.js`.
- Progress is stored in SQLite and is suitable for single-instance hosting, not high-scale multi-instance sync.
- Lesson PDF generation depends on Playwright or ReportLab and is optional for MVP.

## Phase Map

| Phase | Name | Outcome |
| --- | --- | --- |
| 0 | Discovery and Freeze | Confirm scope, audit current behavior, prevent moving targets |
| 1 | Backend Refactor and API Contracts | Make the Flask app mobile-consumable |
| 2 | Mobile UX and Technical Design | Lock screen map, data flow, and app architecture |
| 3 | Android Foundation | App shell, navigation, auth plumbing, API client, local storage |
| 4 | Read-Only Learning Flows | Dashboard, languages, lessons, vocabulary, resources, progress |
| 5 | Interactive Learning Flows | Quiz, flashcards, SRS review, placement, daily practice |
| 6 | Speech, Audio, and Input | Native TTS playback, dictation, speaking practice |
| 7 | Offline, Sync, and Performance | Cache strategy, failure recovery, app responsiveness |
| 8 | QA, Security, and Release | Test coverage, hardening, Play Store preparation |
| 9 | Launch and Post-Launch | Production rollout, telemetry review, backlog stabilization |

## Phase 0: Discovery and Freeze

### Objective

Create a stable foundation for execution by documenting the current app and freezing the scope of version 1.

### Owners

- Product and Architecture Agent
- Backend API Agent
- Android Foundation Agent

### Work Items

1. Inventory every current user flow in the web app.
2. Classify each feature as `MVP`, `Phase 2`, or `defer`.
3. Record which flows are browser-dependent versus backend-dependent.
4. Capture screenshots and route maps for all major pages.
5. Confirm whether Android must support only authenticated flows or also guest browsing.
6. Decide whether Android login will stay email-only for v1.
7. Decide whether lesson PDF download is required in Android MVP.
8. Decide whether local resource drilling is part of mobile MVP or web-only.

### Deliverables

- Feature inventory
- MVP scope list
- Deferred feature list
- Screen map
- Risk register

### Exit Criteria

- Every existing feature is classified.
- MVP scope is approved.
- No agent starts implementation against undefined scope.

## Phase 1: Backend Refactor and API Contracts

### Objective

Expose stable JSON APIs so Android can consume the product without relying on server-rendered HTML pages.

### Owners

- Backend API Agent
- Content and Data Agent

### Work Items

1. Split `app.py` into logical modules:
   - auth
   - content
   - progress
   - practice engine
   - media
   - feedback
2. Define versioned API routes, for example:
   - `/api/v1/auth/login`
   - `/api/v1/me`
   - `/api/v1/languages`
   - `/api/v1/lessons/<lang>`
   - `/api/v1/lessons/<lang>/<id>`
   - `/api/v1/vocabulary/<lang>`
   - `/api/v1/practice/<lang>/session`
   - `/api/v1/placement/<lang>/session`
   - `/api/v1/quiz/<lang>/<lesson_id>/submit`
   - `/api/v1/review/<lang>/session`
   - `/api/v1/progress`
   - `/api/v1/feedback`
   - `/api/v1/tts`
3. Standardize response shapes for:
   - lessons
   - vocabulary items
   - grammar blocks
   - quiz questions
   - practice questions
   - progress summaries
4. Extract reusable service functions so web templates and JSON APIs call the same logic.
5. Decide session strategy for mobile:
   - keep secure cookie auth if practical
   - or introduce token-based auth for Android
6. Add API validation and error handling with consistent HTTP status codes.
7. Add backend tests around content loading, auth, progress updates, and practice generation.

### Deliverables

- API specification markdown
- Flask route modules
- Shared service layer
- Test coverage for mobile-facing endpoints

### Exit Criteria

- Android can fetch all required learning content without HTML parsing.
- Web flows still work against the same underlying logic.
- API responses are documented and stable.

### Dependencies

- Phase 0 scope approval

## Phase 2: Mobile UX and Technical Design

### Objective

Lock the Android app structure before feature implementation begins.

### Owners

- UI and Design Agent
- Android Foundation Agent
- Product and Architecture Agent

### Work Items

1. Define navigation graph:
   - splash
   - onboarding or login
   - dashboard
   - language home
   - lesson list
   - lesson detail
   - vocabulary
   - quiz
   - practice
   - review
   - dictation
   - speaking
   - progress
   - resources
   - feedback
2. Choose Android stack:
   - Kotlin
   - Jetpack Compose
   - Retrofit or Ktor client
   - Room for local cache
   - Coroutines and Flow
   - WorkManager for sync or cleanup jobs
3. Define app architecture:
   - presentation layer
   - domain layer
   - data layer
   - repository interfaces
4. Define loading, empty, and offline states for every screen.
5. Define how bilingual text is presented on mobile for readability.
6. Decide whether mobile will support portrait only in MVP.

### Deliverables

- Screen flow diagram
- Component architecture doc
- Data model mapping doc
- Mobile design tokens and UI patterns

### Exit Criteria

- Android agents can build screens without inventing behavior.
- Backend and Android agree on data contracts.

### Dependencies

- Phase 1 API shape draft

## Phase 3: Android Foundation

### Objective

Build the app skeleton and core platform capabilities.

### Owners

- Android Foundation Agent
- UI and Design Agent

### Work Items

1. Create Android project structure.
2. Set up environment configuration for dev, staging, and production base URLs.
3. Implement navigation framework.
4. Implement API client, request interceptors, and error mapping.
5. Implement login flow and session persistence.
6. Add Room database for local caches:
   - lessons
   - vocabulary
   - lightweight progress snapshots
7. Create reusable Compose components:
   - app scaffold
   - cards
   - progress bars
   - CTA buttons
   - content chips
   - audio buttons
8. Add analytics and logging hooks if approved.

### Deliverables

- Running Android shell app
- Login flow
- API client
- Local persistence layer
- Base design system

### Exit Criteria

- User can install the app, sign in, and reach the dashboard.
- App handles network errors without crashing.

### Dependencies

- Phase 2 design approval
- Minimum backend auth APIs from Phase 1

## Phase 4: Read-Only Learning Flows

### Objective

Deliver the first useful Android version with browseable content and progress visibility.

### Owners

- Android Learning Features Agent
- Backend API Agent
- Content and Data Agent

### Work Items

1. Dashboard
   - streak summary
   - XP summary
   - continue learning CTA
   - quick links to French and Spanish
2. Language pages
   - CEFR grouping
   - lesson counts
   - next lesson recommendations
3. Lesson detail
   - title
   - description
   - vocabulary section
   - grammar section
4. Vocabulary explorer
   - search
   - category filters
   - item detail cards
5. Resources screen
6. Progress screen
7. Translation utility if included in MVP

### Deliverables

- Browseable Android content flows
- Cached lesson and vocabulary data
- Progress summary screens

### Exit Criteria

- Android can replace the web app for read-only learning consumption.
- Content renders correctly for English, Bengali, French, and Spanish text.

### Dependencies

- Phase 3 complete
- Content APIs stable

## Phase 5: Interactive Learning Flows

### Objective

Port the core learning loops that drive retention and engagement.

### Owners

- Android Learning Features Agent
- Backend API Agent
- Content and Data Agent

### Work Items

1. Quiz flow
   - question rendering
   - scoring
   - answer review
   - completion submission
2. Flashcards
   - flip interaction
   - know or review decisions
   - progress updates
3. SRS review
   - due words
   - box advancement
   - next due scheduling
4. Placement test
   - session generation
   - level scoring
   - recommendation display
5. Daily practice
   - MCQ
   - typing
   - sentence ordering
   - context questions if kept in scope

### Deliverables

- Android practice engine screens
- Progress sync with backend
- Stable question rendering across modes

### Exit Criteria

- A user can learn, answer, review, and update progress fully inside Android.
- Results match current backend rules.

### Dependencies

- Phase 1 practice APIs
- Phase 4 content rendering complete

## Phase 6: Speech, Audio, and Input

### Objective

Replace browser-only speech behavior with native Android audio and microphone flows.

### Owners

- Speech and Media Agent
- Android Learning Features Agent
- Backend API Agent

### Work Items

1. TTS playback
   - consume server TTS endpoint
   - cache audio locally where useful
   - handle replay and queue control
2. Dictation mode
   - play prompt audio
   - capture typed answer
   - accent-tolerant answer checking through backend or shared logic
3. Speaking mode
   - request mic permission
   - run speech recognition using Android-native APIs
   - compare recognized text to target phrases
4. Error handling for:
   - no microphone permission
   - unsupported device services
   - network failures during TTS
5. Accessibility checks for audio controls and transcripts

### Deliverables

- Native audio subsystem
- Dictation experience
- Speaking practice experience

### Exit Criteria

- Android no longer depends on browser speech APIs.
- Audio and mic flows are production-safe on real devices.

### Dependencies

- Phase 5 base learning flows complete
- Backend support for answer checking where needed

## Phase 7: Offline, Sync, and Performance

### Objective

Make the mobile app resilient in real-world connectivity conditions.

### Owners

- Android Foundation Agent
- Backend API Agent
- QA and Release Agent

### Work Items

1. Define offline policy:
   - what content is cached
   - what actions require network
   - what updates queue locally
2. Cache lessons and vocabulary for offline reading.
3. Queue progress writes when offline if accepted by product.
4. Reconcile sync conflicts for progress and review updates.
5. Optimize startup time, image loading, JSON parsing, and screen transitions.
6. Add retry logic and user-visible sync status.

### Deliverables

- Offline behavior spec
- Local cache implementation
- Sync queue where required
- Performance benchmark results

### Exit Criteria

- App remains usable on unstable mobile networks.
- No silent data loss during reconnect.

### Dependencies

- Core interactive flows complete

## Phase 8: QA, Security, and Release

### Objective

Stabilize the app for public distribution.

### Owners

- QA and Release Agent
- Backend API Agent
- Android Foundation Agent

### Work Items

1. Build test matrix:
   - Android OS versions
   - screen sizes
   - low-memory devices
   - slow networks
2. Run backend API regression suite.
3. Add Android unit tests and UI tests for critical flows.
4. Verify auth/session security and transport settings.
5. Review secret handling and environment configuration.
6. Validate crash reporting and logging strategy.
7. Prepare Play Store assets:
   - app name
   - icon
   - screenshots
   - privacy policy
   - content rating
8. Create release checklist for staging and production.

### Deliverables

- Test reports
- Security checklist
- Release candidate build
- Play Store submission package

### Exit Criteria

- Critical paths pass on physical devices.
- Release checklist is fully signed off.

### Dependencies

- All required MVP phases complete

## Phase 9: Launch and Post-Launch

### Objective

Control the rollout and use production feedback to prioritize the next iteration.

### Owners

- Product and Architecture Agent
- QA and Release Agent
- Android Foundation Agent

### Work Items

1. Launch internal alpha.
2. Fix high-severity issues.
3. Launch closed beta.
4. Collect feedback from real learners.
5. Compare Android retention and completion patterns with the web app.
6. Prioritize post-launch backlog:
   - push notifications
   - richer offline mode
   - downloadable lesson PDFs
   - account upgrades
   - advanced analytics

### Deliverables

- Launch report
- Beta issue log
- Version 1.1 backlog

### Exit Criteria

- Production rollout is stable.
- Next cycle priorities are documented using real usage data.

## Suggested MVP Scope

These items should be in the first Android release unless product changes direction:

- Login
- Dashboard
- Language selection
- Lesson list
- Lesson detail
- Vocabulary
- Quiz
- Flashcards
- SRS review
- Daily practice without the most complex optional modes if needed
- Placement test
- Progress
- Feedback
- Server TTS playback

These items can be deferred if schedule pressure rises:

- Lesson PDF download
- Resource drill based on local private PDFs
- Full offline write-sync
- Advanced speech scoring
- Theme customization parity with web

## Recommended Build Order for Agents

If several agents work in parallel, use this sequence:

1. Architecture Agent finalizes MVP scope and dependencies.
2. Backend API Agent exposes lesson, vocabulary, auth, and progress APIs.
3. Android Foundation Agent builds shell, login, navigation, and networking.
4. UI and Design Agent defines screen system and reusable components.
5. Android Learning Features Agent ships read-only flows.
6. Backend API Agent finishes practice and review endpoints.
7. Android Learning Features Agent ships interactive flows.
8. Speech and Media Agent implements TTS, dictation, and speaking.
9. QA and Release Agent hardens the product and prepares release.

## Handoff Checklist Between Agents

Every agent handoff should include:

- branch or artifact reference
- changed endpoints or screens
- known blockers
- test evidence
- assumptions that were made
- items intentionally deferred

## Definition of Done for the Full Project

The project is done when all of the following are true:

1. Android users can complete core learning journeys without opening the web app.
2. Web and Android use shared backend rules for content and progress.
3. Auth, progress, quiz, and review flows work reliably on real devices.
4. Speech and audio features are either production-ready or explicitly deferred from MVP.
5. The Play Store release package is complete and approved.
6. Post-launch monitoring and a follow-up backlog exist.

## Immediate Next Actions

Start with these agent assignments first:

1. Assign one agent to produce the API contract document from the current Flask app.
2. Assign one agent to define the Android navigation graph and screen inventory.
3. Assign one agent to split the monolithic backend into service-ready modules without changing behavior.
4. Assign one agent to create the Android foundation project with Compose, networking, and local storage.

These four tracks create the minimum foundation needed for the rest of the project.
