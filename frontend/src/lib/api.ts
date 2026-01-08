import axios from "axios";

// Standard production-ready API client
export const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
    headers: {
        "Content-Type": "application/json",
    },
    timeout: 120000,
});

// Request Logger
api.interceptors.request.use(request => {
    // Ensure URL doesn't start with a slash if baseURL is set
    // though Axios handles this, we're being explicit
    const fullPath = `${request.baseURL}${request.url?.startsWith('/') ? request.url : `/${request.url}`}`;
    console.log(`[API Request] ${request.method?.toUpperCase()} ${fullPath}`);
    return request;
});

// Response Logger
api.interceptors.response.use(
    (response) => {
        console.log(`[API Response] ${response.status} ${response.config.url}`);
        return response;
    },
    (error) => {
        console.error(`[API Error] ${error.config?.url}: ${error.message}`);
        return Promise.reject(error);
    }
);
