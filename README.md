# GovBot

A Government Chatbot for Khyber Pakhtunkhwa (KPK), Pakistan - An AI-powered RAG (Retrieval-Augmented Generation) system that provides information about government policies, programs, and services.

## Features

- **RAG Pipeline**: Advanced retrieval-augmented generation using Qdrant vector database
- **AI-Powered**: Integrated with Google Gemini for intelligent responses
- **Government Focus**: Specialized in KPK government information and services
- **Modern UI**: Built with React, TypeScript, and Tailwind CSS
- **Serverless**: Deployed on Vercel with serverless functions

## Getting Started

To run this project locally:

1. Install dependencies:
   ```bash
   npm install
   ```

2. Set up environment variables:
   Create a `.env` file with:
   ```
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_qdrant_api_key
   GEMINI_API_KEY=your_gemini_api_key
   COLLECTION_NAME=GovTech
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to `http://localhost:5173`

## Project Structure

- `src/` - React frontend components and application logic
- `api/` - Vercel serverless functions (FastAPI backend)
- `public/` - Static assets
- `backend/` - Original FastAPI backend (for reference)

## Technologies Used

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Shadcn UI
- **Backend**: FastAPI, Python 3.9
- **AI/ML**: Google Gemini, Sentence Transformers, Qdrant Vector DB
- **Deployment**: Vercel (Frontend + Serverless Functions)

## Deployment

This project is configured for Vercel deployment:

```bash
npm run build
```

The project uses Vercel serverless functions for the backend API, making it fully serverless and scalable.

## API Endpoints

- `GET /api/` - Health check
- `POST /api/chat` - Main chat endpoint for RAG pipeline
- `GET /api/health` - Detailed health check

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
