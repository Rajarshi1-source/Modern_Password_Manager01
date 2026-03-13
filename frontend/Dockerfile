FROM node:18-alpine

# Set work directory
WORKDIR /app

# Copy package files
# Switch early to avoid root-owned files
COPY --chown=node:node package*.json ./

# Install dependencies
RUN npm ci

# Copy project files
COPY --chown=node:node . .

# Switch to non-root user
USER node

# Health check AFTER user switch
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5173/health || exit 1

# Default command (development)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# For production build, use:
# RUN npm run build
# FROM nginx:alpine
# COPY --from=0 /app/dist /usr/share/nginx/html
# EXPOSE 80
# CMD ["nginx", "-g", "daemon off;"]

