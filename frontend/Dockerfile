# Stage 1: Build the Vite React app
FROM node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Railway injects env vars as build args automatically
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy built assets from Stage 1
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx config template (uses ${PORT} for Railway)
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template

# Remove the default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# At runtime: substitute ${PORT} in the template, then start nginx
CMD ["sh", "-c", "envsubst '$PORT' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
