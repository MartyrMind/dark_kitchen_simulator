FROM golang:1.22-alpine AS builder

WORKDIR /src

COPY services/kitchen-scheduler-worker/go.mod services/kitchen-scheduler-worker/go.sum* ./
RUN go mod download

COPY services/kitchen-scheduler-worker ./

RUN CGO_ENABLED=0 GOOS=linux go build -o /out/kitchen-scheduler-worker ./cmd/worker

FROM alpine:3.20

WORKDIR /app

COPY --from=builder /out/kitchen-scheduler-worker /app/kitchen-scheduler-worker

EXPOSE 9090

CMD ["/app/kitchen-scheduler-worker"]
