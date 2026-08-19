import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const DESCRIPTIONS = [
  "A Python Flask web application with PostgreSQL database and Redis cache",
  "A Node.js microservice that processes messages from RabbitMQ",
  "A Java Spring Boot REST API with MySQL backend and Elasticsearch",
  "A Go gRPC service with MongoDB and Prometheus metrics",
  "A static website served by nginx with TLS termination",
  "A Python Celery worker that processes image uploads with S3 storage",
  "A Ruby on Rails app with Sidekiq background jobs and PostgreSQL",
];

export const options = {
  stages: [
    { duration: "30s", target: 5 },
    { duration: "1m", target: 5 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    "http_req_duration{name:health}": ["p(95)<200"],
    "http_req_duration{name:generate}": ["p(95)<120000"],
    "http_req_failed": ["rate<0.1"],
  },
};

export default function () {
  const healthRes = http.get(`${BASE_URL}/health`, {
    tags: { name: "health" },
  });
  check(healthRes, {
    "health status is 200": (r) => r.status === 200,
    "health body is ok": (r) => r.json().status === "ok",
  });

  const description = DESCRIPTIONS[__VU % DESCRIPTIONS.length];
  const payload = JSON.stringify({
    description: description,
    namespace: "load-test",
    replicas: 2,
  });

  const generateRes = http.post(`${BASE_URL}/generate`, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { name: "generate" },
    timeout: "120s",
  });

  check(generateRes, {
    "generate status is 200": (r) => r.status === 200,
    "generate has final_manifests": (r) =>
      r.json().final_manifests !== undefined,
    "generate has trace_id": (r) => r.json().trace_id !== null,
  });

  sleep(1);
}
