// API Configuration
// Check if we're on localhost (development on Mac) or remote IP (iPhone/mobile)
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

export const API_BASE_URL = isLocalhost
  ? '' // Use proxy when on localhost
  : 'http://192.168.10.120:5001'; // Direct backend connection when on mobile/network IP

export const getApiUrl = (path) => {
  const url = `${API_BASE_URL}${path}`;
  console.log('API URL:', url);
  return url;
};
