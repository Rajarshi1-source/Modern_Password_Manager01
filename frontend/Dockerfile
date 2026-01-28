FROM node:18-alpine

# Set work directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy project files
COPY . .

# Expose port
EXPOSE 5173

# Fix permissions for node user
RUN chown -R node:node /app

# Switch to non-root user
USER node

# Default command (development)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# For production build, use:
# RUN npm run build
# FROM nginx:alpine
# COPY --from=0 /app/dist /usr/share/nginx/html
# EXPOSE 80
# CMD ["nginx", "-g", "daemon off;"]

