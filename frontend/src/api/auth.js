import request from '../utils/request';

export const loginApi = (payload) => request.post('/auth/login', payload);
export const registerApi = (payload) => request.post('/auth/register', payload);
export const profileApi = () => request.get('/auth/profile');
export const updateProfileApi = (payload) => request.put('/auth/profile', payload);
export const teacherListApi = (params = {}) => request.get('/teachers', { params });

