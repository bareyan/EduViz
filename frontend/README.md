# EduViz Frontend

The frontend for EduViz is a modern, responsive React application built with TypeScript and Vite. It provides an intuitive interface for users to upload content, configure video generation options, and view results.

## Quick Start

### Prerequisites
- Node.js 18+ (LTS recommended)
- npm or yarn

### Local Development Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Start the Development Server:**
    ```bash
    npm run dev
    ```
    The application will be available at `http://localhost:3000`.

### Building for Production

To create a production build:

```bash
npm run build
```

The output will be in the `dist` directory.

### Preview Production Build

To preview the production build locally:

```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── App.tsx                   # Main application component & Routing
│   ├── main.tsx                  # Application entry point
│   ├── index.css                 # Global styles (Tailwind)
│   ├── pages/                    # Route components (Views)
│   │   ├── HomePage.tsx          # Upload interface
│   │   ├── AnalysisPage.tsx      # Topic selection
│   │   ├── GenerationPage.tsx    # Video generation process
│   │   ├── ResultsPage.tsx       # Video playback
│   │   ├── EditPage.tsx          # Section editing
│   │   ├── GalleryPage.tsx       # Job gallery
│   │   └── LoginPage.tsx         # Authentication
│   ├── features/                 # Feature-specific components
│   ├── services/                 # API client services (axios)
│   ├── hooks/                    # Custom React hooks
│   ├── types/                    # TypeScript interfaces
│   ├── config/                   # Configuration constants
│   └── components/               # Shared UI components
```

## Scripts

| Script | Description |
| :--- | :--- |
| `npm run dev` | Starts the Vite development server |
| `npm run build` | Compiles TypeScript and builds for production |
| `npm run lint` | Runs ESLint to check for code quality issues |
| `npm run preview` | Serves the production build locally |

## Configuration

The frontend communicates with the backend API. By default, it expects the backend to be running on `http://localhost:8000`. This is configured in `src/config/api.config.ts`.

## Tech Stack

-   **React 18:** Component-based UI library
-   **TypeScript:** Static typing for JavaScript
-   **Vite:** High-performance build tool
-   **Tailwind CSS:** Utility-first CSS framework
-   **React Router:** Client-side routing
-   **Axios:** Promise-based HTTP client
-   **Lucide React:** Icon library

Refer to the root `ARCHITECTURE.md` for architectural details.
