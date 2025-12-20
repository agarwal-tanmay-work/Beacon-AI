import axios from "axios";

// Create Axios Instance
export const api = axios.create({
    baseURL: "http://127.0.0.1:8000/api/v1", // Using IP for absolute reliability
    headers: {
        "Content-Type": "application/json",
    },
});

// Request Interceptor
api.interceptors.request.use(request => {
    console.log('Starting Request', request.baseURL, request.url);
    return request;
});

// Response Interceptor for generic error handling
api.interceptors.response.use(
    (response) => {
        console.log('Response:', response.status);
        return response;
    },
    (error) => {
        console.error("API Error Detailed:", error.config?.url, error.response?.status, error.message);
        return Promise.reject(error);
    }
);
