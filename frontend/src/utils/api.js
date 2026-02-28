/**
 * Centralized API utility for making authenticated requests
 */

/**
 * Make an authenticated API request
 * @param {string} url - The API endpoint
 * @param {object} options - Fetch options (method, body, headers, etc.)
 * @returns {Promise<Response>} - The fetch response
 */
export const apiRequest = async (url, options = {}) => {
  const token = localStorage.getItem('access_token')

  // Prepare headers
  const headers = {
    ...options.headers,
  }

  // Add Authorization header if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Add Content-Type for JSON if body is an object (not FormData)
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  // Make the request
  const response = await fetch(url, {
    ...options,
    headers,
  })

  // Handle 401 Unauthorized - redirect to login
  if (response.status === 401) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    window.location.href = '/'
  }

  return response
}

/**
 * Make a GET request
 */
export const apiGet = async (url, options = {}) => {
  return apiRequest(url, {
    ...options,
    method: 'GET',
  })
}

/**
 * Make a POST request
 */
export const apiPost = async (url, body, options = {}) => {
  return apiRequest(url, {
    ...options,
    method: 'POST',
    body: body instanceof FormData ? body : JSON.stringify(body),
  })
}

/**
 * Make a PUT request
 */
export const apiPut = async (url, body, options = {}) => {
  return apiRequest(url, {
    ...options,
    method: 'PUT',
    body: body instanceof FormData ? body : JSON.stringify(body),
  })
}

/**
 * Make a DELETE request
 */
export const apiDelete = async (url, options = {}) => {
  return apiRequest(url, {
    ...options,
    method: 'DELETE',
  })
}
