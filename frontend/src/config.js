// API Configuration – reads from Vite env in the browser
const API_BASE_URL = (
	(typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
	(typeof process !== 'undefined' && process.env?.VITE_API_URL) ||
	'/api'
);

export default API_BASE_URL;
