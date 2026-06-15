FROM node:20-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
