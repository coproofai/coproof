# STAGE 1: Build
FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build -- --configuration=production

# STAGE 2: Serve
FROM nginx:stable-alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist/frontend/ /tmp/dist/
RUN if [ -d /tmp/dist/browser ]; then cp -r /tmp/dist/browser/. /usr/share/nginx/html/; else cp -r /tmp/dist/. /usr/share/nginx/html/; fi

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
