# Job Search Platform VS Code Extension Design

## Overview

This document outlines the design for a VS Code extension that will provide a rich, interactive user interface for the Job Search Automation Platform. The extension will use VS Code's WebView API to create custom UI panels that interact with the platform's REST API (as defined in `API.md`).

## Architecture

```
┌─────────────────────────────────────────────┐
│                VS Code                       │
│  ┌─────────────┐        ┌────────────────┐  │
│  │ Job Search  │        │                │  │
│  │ Extension   │◄──────►│ WebView Panels │  │
│  │ (TypeScript)│        │ (HTML/CSS/JS)  │  │
│  └─────────────┘        └────────────────┘  │
└───────────┬─────────────────────────┬───────┘
            │                         │
            ▼                         ▼
┌───────────────────┐      ┌─────────────────────┐
│ Job Search API    │      │ Document Storage    │
│ (FastAPI)         │      │ (Local Files & GCS) │
└───────────────────┘      └─────────────────────┘
```

## Extension Components

### 1. Activity Bar View Container

The extension will contribute a custom view container to the VS Code activity bar:

- **Icon**: Custom job search icon
- **Title**: "Job Search"
- **Views**:
  - Job Dashboard
  - Strategy Planner
  - Profile Manager
  - Document Generator

### 2. WebView Panels

The extension will use WebView panels to create rich interactive interfaces:

#### 2.1 Job Dashboard Panel

```
┌───────────────────────────────────────────────────────┐
│ Job Search Dashboard                           [_][X] │
├───────────────────────────────────────────────────────┤
│ ┌─────────────────┐ ┌───────────────────────────────┐ │
│ │ Search          │ │ Filters                       │ │
│ │ ┌─────────────┐ │ │ ┌─────────┐  ┌─────────────┐  │ │
│ │ │ Search...   │ │ │ │ Location│  │ Remote Only │  │ │
│ │ └─────────────┘ │ │ └─────────┘  └─────────────┘  │ │
│ └─────────────────┘ └───────────────────────────────┘ │
│                                                       │
│ Results: 5 jobs found                                 │
│ ┌───────────────────────────────────────────────────┐ │
│ │ Senior Cloud Architect - Amazon AWS               │ │
│ │ Match: 95% │ Priority: High │ Seattle, WA         │ │
│ │ [View Details] [Generate Documents] [Apply]        │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────┐ │
│ │ DevOps Engineer - Microsoft                       │ │
│ │ Match: 87% │ Priority: Medium │ Remote            │ │
│ │ [View Details] [Generate Documents] [Apply]        │ │
│ └───────────────────────────────────────────────────┘ │
│ ...                                                   │
└───────────────────────────────────────────────────────┘
```

#### 2.2 Strategy Planner Panel

```
┌───────────────────────────────────────────────────────┐
│ Job Search Strategy                            [_][X] │
├───────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐   │
│ │ Today's Focus: Apply to 3 high-priority cloud   │   │
│ │ architecture roles and follow up on pending     │   │
│ │ applications                                    │   │
│ └─────────────────────────────────────────────────┘   │
│                                                       │
│ Priority Actions                                      │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ☐ Apply to Amazon AWS position                  │   │
│ │ ☐ Complete cloud certification practice exam    │   │
│ │ ☐ Follow up on Microsoft application            │   │
│ └─────────────────────────────────────────────────┘   │
│                                                       │
│ Recommended Jobs                                      │
│ ┌─────────────────────────────────────────────────┐   │
│ │ [Job Cards with quick action buttons]           │   │
│ └─────────────────────────────────────────────────┘   │
│                                                       │
│ [Generate New Strategy] [Export to Markdown]          │
└───────────────────────────────────────────────────────┘
```

#### 2.3 Profile Manager Panel

```
┌───────────────────────────────────────────────────────┐
│ Profile Manager                                [_][X] │
├───────────────────────────────────────────────────────┤
│ ┌───────────────┐  ┌────────────────────────────────┐ │
│ │ Profile       │  │ Experience                     │ │
│ │ Summary       │  │ ┌────────────────────────────┐ │ │
│ │               │  │ │ Company: Clover            │ │ │
│ │ [Edit]        │  │ │ Title: Infra Architect     │ │ │
│ │               │  │ │ Dates: 2020-2023           │ │ │
│ │               │  │ │ Description: [...]         │ │ │
│ │               │  │ │                            │ │ │
│ │               │  │ │ [Edit]   [Delete]          │ │ │
│ │               │  │ └────────────────────────────┘ │ │
│ └───────────────┘  │ [+ Add Experience]             │ │
│                    └────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────┐ │
│ │ Skills                                            │ │
│ │ ┌─────────┐ ┌──────────┐ ┌─────────────┐ ┌──────┐ │ │
│ │ │ AWS     │ │ Terraform│ │ Kubernetes  │ │ GCP  │ │ │
│ │ └─────────┘ └──────────┘ └─────────────┘ └──────┘ │ │
│ │ [+ Add Skill]                                     │ │
│ └───────────────────────────────────────────────────┘ │
│                                                       │
│ [Upload Resume] [Upload Cover Letter] [Combine Data]  │
└───────────────────────────────────────────────────────┘
```

#### 2.4 Document Generator Panel

```
┌───────────────────────────────────────────────────────┐
│ Document Generator                             [_][X] │
├───────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐ ┌─────────────────────┐   │
│ │ Job Selection           │ │ Options             │   │
│ │ ┌─────────────────────┐ │ │                     │   │
│ │ │ [Select Job ▼]      │ │ │ ☑ Visual Resume     │   │
│ │ └─────────────────────┘ │ │ ☑ Writing Pass      │   │
│ │                         │ │ ☐ Include Projects  │   │
│ │ OR                      │ │                     │   │
│ │                         │ │                     │   │
│ │ [Use Selected Job]      │ │                     │   │
│ └─────────────────────────┘ └─────────────────────┘   │
│                                                       │
│ [Generate Documents]                                  │
│                                                       │
│ Recent Documents                                      │
│ ┌───────────────────────────────────────────────────┐ │
│ │ Resume - Amazon AWS - 04/20/2025                  │ │
│ │ [View] [Download] [Edit]                          │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────┐ │
│ │ Cover Letter - Microsoft - 04/19/2025             │ │
│ │ [View] [Download] [Edit]                          │ │
│ └───────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

## Technical Implementation

### Extension Structure

```
jobsearch-vscode/
├── package.json            # Extension manifest
├── tsconfig.json           # TypeScript configuration
├── src/
│   ├── extension.ts        # Extension activation point
│   ├── panels/             # WebView panel implementations
│   │   ├── dashboardPanel.ts
│   │   ├── strategyPanel.ts
│   │   ├── profilePanel.ts
│   │   └── documentPanel.ts
│   ├── api/                # API client implementation
│   │   ├── apiClient.ts    # Wrapper for API endpoints
│   │   ├── jobsApi.ts      # Jobs endpoints
│   │   ├── profileApi.ts   # Profile endpoints
│   │   └── documentsApi.ts # Document endpoints
│   ├── views/              # TreeView implementations
│   │   ├── jobsTreeView.ts
│   │   └── documentsTreeView.ts
│   └── utils/              # Utility functions
├── media/                  # Icons and assets
└── webview-ui/             # WebView HTML/CSS/JS
    ├── shared/             # Shared UI components
    ├── dashboard/          # Dashboard UI files
    ├── strategy/           # Strategy UI files
    ├── profile/            # Profile UI files
    └── documents/          # Documents UI files
```

### Key Extension Features

1. **API Integration**
   ```typescript
   // apiClient.ts example
   export class ApiClient {
     private baseUrl: string;
     
     constructor(baseUrl: string = "http://localhost:8000") {
       this.baseUrl = baseUrl;
     }
     
     async searchJobs(keywords: string, limit: number = 10): Promise<Job[]> {
       const response = await fetch(`${this.baseUrl}/api/jobs/search?keywords=${encodeURIComponent(keywords)}&limit=${limit}`);
       if (!response.ok) {
         throw new Error(`API error: ${response.status}`);
       }
       return response.json();
     }
     
     // Additional API methods...
   }
   ```

2. **WebView Communications**
   ```typescript
   // dashboardPanel.ts example
   export class DashboardPanel {
     private static currentPanel: DashboardPanel | undefined;
     private readonly _panel: vscode.WebviewPanel;
     private readonly _extensionUri: vscode.Uri;
     private readonly _apiClient: ApiClient;
     private _disposables: vscode.Disposable[] = [];
     
     private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
       this._panel = panel;
       this._extensionUri = extensionUri;
       this._apiClient = new ApiClient();
       
       // Set initial HTML content
       this._panel.webview.html = this._getWebviewContent();
       
       // Handle messages from the webview
       this._panel.webview.onDidReceiveMessage(
         async (message) => {
           switch (message.command) {
             case 'searchJobs':
               try {
                 const jobs = await this._apiClient.searchJobs(message.keywords, message.limit);
                 this._panel.webview.postMessage({ command: 'jobResults', jobs });
               } catch (error) {
                 vscode.window.showErrorMessage(`Error searching jobs: ${error}`);
               }
               break;
             // Other message handlers...
           }
         },
         null,
         this._disposables
       );
     }
     
     // Static create method and other implementation...
   }
   ```

3. **WebView HTML Generation**
   ```typescript
   private _getWebviewContent(): string {
     const webview = this._panel.webview;
     const scriptUri = webview.asWebviewUri(
       vscode.Uri.joinPath(this._extensionUri, 'webview-ui', 'dashboard', 'main.js')
     );
     const styleUri = webview.asWebviewUri(
       vscode.Uri.joinPath(this._extensionUri, 'webview-ui', 'dashboard', 'style.css')
     );
     
     return `<!DOCTYPE html>
     <html lang="en">
     <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <link href="${styleUri}" rel="stylesheet">
       <title>Job Dashboard</title>
     </head>
     <body>
       <div class="container">
         <header>
           <h1>Job Search Dashboard</h1>
         </header>
         <div class="search-container">
           <input id="searchInput" placeholder="Search for jobs..." />
           <button id="searchButton">Search</button>
         </div>
         <div id="filterContainer">
           <!-- Filters UI -->
         </div>
         <div id="resultsContainer">
           <!-- Results will be populated here -->
         </div>
       </div>
       <script src="${scriptUri}"></script>
     </body>
     </html>`;
   }
   ```

4. **Client-side JavaScript**
   ```javascript
   // main.js example for dashboard
   (function() {
     // Get VS Code webview API
     const vscode = acquireVsCodeApi();
     
     // Elements
     const searchInput = document.getElementById('searchInput');
     const searchButton = document.getElementById('searchButton');
     const resultsContainer = document.getElementById('resultsContainer');
     
     // Add event listeners
     searchButton.addEventListener('click', () => {
       const keywords = searchInput.value;
       vscode.postMessage({
         command: 'searchJobs',
         keywords,
         limit: 10
       });
       
       // Show loading indicator
       resultsContainer.innerHTML = '<div class="loading">Searching...</div>';
     });
     
     // Handle messages from the extension
     window.addEventListener('message', event => {
       const message = event.data;
       switch (message.command) {
         case 'jobResults':
           displayJobResults(message.jobs);
           break;
         // Other message handlers...
       }
     });
     
     function displayJobResults(jobs) {
       if (jobs.length === 0) {
         resultsContainer.innerHTML = '<div class="no-results">No jobs found</div>';
         return;
       }
       
       resultsContainer.innerHTML = `
         <div class="results-header">
           <h3>${jobs.length} jobs found</h3>
         </div>
         <div class="job-list">
           ${jobs.map(job => createJobCard(job)).join('')}
         </div>
       `;
       
       // Attach event handlers to buttons
       document.querySelectorAll('.job-card .btn-details').forEach(btn => {
         btn.addEventListener('click', (event) => {
           const jobId = event.target.dataset.jobId;
           vscode.postMessage({
             command: 'viewJobDetails',
             jobId
           });
         });
       });
       
       // More event handlers...
     }
     
     function createJobCard(job) {
       return `
         <div class="job-card">
           <div class="job-header">
             <h4>${job.title}</h4>
             <div class="job-company">${job.company}</div>
           </div>
           <div class="job-meta">
             <span class="job-match">Match: ${job.match_score}%</span>
             <span class="job-priority">Priority: ${job.application_priority}</span>
             <span class="job-location">${job.location || 'Remote'}</span>
           </div>
           <div class="job-actions">
             <button class="btn-details" data-job-id="${job.id}">View Details</button>
             <button class="btn-generate" data-job-id="${job.id}">Generate Documents</button>
             <button class="btn-apply" data-job-id="${job.id}">Apply</button>
           </div>
         </div>
       `;
     }
   })();
   ```

## API Integration

The extension will integrate with the Job Search Platform API as defined in `API.md`. Key integrations include:

### Jobs API Integration

- **Search Jobs**: `GET /api/jobs/search`
- **Get Job Details**: `GET /api/jobs/{job_id}`
- **Mark Applied**: `POST /api/jobs/{job_id}/apply`

### Profile API Integration

- **Get Profile Summary**: `GET /api/profile/summary`
- **Update Skills**: `POST /api/profile/skills`
- **Upload Resume**: `POST /api/profile/upload/resume`

### Document API Integration

- **Generate Documents**: `POST /api/documents/generate`
- **List Documents**: `GET /api/documents/list`
- **Download Document**: `GET /api/documents/{document_id}/download`

### Strategy API Integration

- **Generate Strategy**: `POST /api/strategies/generate`
- **Get Latest Strategy**: `GET /api/strategies/latest`

## Development Workflow

1. **Setup Development Environment**
   - Node.js and npm for VS Code extension development
   - Python environment for running the Job Search Platform API

2. **Development Process**
   - Use VS Code Extension Yeoman Generator to scaffold the project
   - Implement extension functionality in TypeScript
   - Create WebView UI in HTML/CSS/JavaScript
   - Test integration with the Job Search Platform API

3. **Testing**
   - Unit tests for extension functionality
   - Integration tests for API communication
   - Manual testing in VS Code Extension Development Host

4. **Publishing**
   - Package the extension using `vsce`
   - Publish to VS Code Marketplace or distribute internally

## User Experience Flow

1. **Install Extension**
   - User installs extension from VS Code Marketplace or VSIX file
   - Extension activates when user selects Job Search from activity bar

2. **Initial Setup**
   - User configures API endpoint in settings
   - Extension validates connection to the API
   - Profile data is loaded from the API

3. **Daily Usage**
   - User opens Job Dashboard to search and track jobs
   - User generates daily strategy from Strategy Planner
   - User updates profile information as needed
   - User generates tailored documents for job applications

## Configuration Options

The extension will support the following configuration options:

```json
{
  "jobSearchExtension.apiEndpoint": "http://localhost:8000",
  "jobSearchExtension.documentStoragePath": "${workspaceFolder}/applications",
  "jobSearchExtension.refreshInterval": 60,
  "jobSearchExtension.notifications": {
    "newJobs": true,
    "applicationDeadlines": true,
    "strategyReminders": true
  }
}
```

## Advantages Over MCP Approach

While the MCP server approach offers a conversational interface through GitHub Copilot, this WebView-based extension provides several advantages:

1. **Rich Visual Interface**: Customized UI with job cards, charts, and interactive elements
2. **Direct Interaction**: Point-and-click interaction without relying on natural language
3. **Persistent Views**: Information remains visible without scrolling through chat history
4. **Offline Capability**: Can cache data for viewing when offline
5. **Comprehensive Integration**: Full access to VS Code UI capabilities (TreeViews, panels, etc.)
6. **No Requirements for Copilot**: Works for users without GitHub Copilot subscription

## Implementation Plan

1. **Phase 1: Core Extension Framework (Week 1)**
   - Create extension structure
   - Implement API client layer
   - Create basic WebView panel infrastructure

2. **Phase 2: Job Dashboard (Week 2)**
   - Implement job search interface
   - Create job cards and detail views
   - Add job action functionality

3. **Phase 3: Profile Management (Week 3)**
   - Create profile display and edit forms
   - Implement resume/cover letter upload
   - Add skill management

4. **Phase 4: Document Generation (Week 4)**
   - Add document generation interface
   - Create document preview and download
   - Implement document history

5. **Phase 5: Strategy Planner (Week 5)**
   - Implement strategy generation interface
   - Create visualization of priorities
   - Add action tracking

6. **Phase 6: Testing and Refinement (Week 6)**
   - Perform comprehensive testing
   - Address UX issues
   - Package for distribution

## Conclusion

This VS Code extension will provide a rich, interactive interface to the Job Search Automation Platform, making it seamlessly integrated into the development environment. By using WebView technology, we can create a custom UI that's both powerful and user-friendly, while maintaining direct integration with the existing API.

The extension will enable users to manage their job search process without leaving VS Code, from searching for jobs to generating application materials and tracking their progress.