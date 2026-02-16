# Build stage for frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Build the app
RUN npm run build

# Production stage - serve static files
FROM nginx:alpine AS runner

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

# nginx serves static files
CMD ["nginx", "-g", "daemon off;"]
