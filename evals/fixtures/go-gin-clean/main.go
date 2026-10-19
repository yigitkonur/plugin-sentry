package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"

	"example.com/api/internal/jobs"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/robfig/cron/v3"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	pool, err := pgxpool.New(context.Background(), os.Getenv("DATABASE_URL"))
	if err != nil {
		slog.Error("db connect failed", "err", err)
		os.Exit(1)
	}
	defer pool.Close()

	c := cron.New()
	_, _ = c.AddFunc("@hourly", func() { jobs.Cleanup(context.Background(), pool) })
	c.Start()

	r := gin.Default()
	r.GET("/healthz", func(ctx *gin.Context) {
		ctx.JSON(http.StatusOK, gin.H{"ok": true})
	})
	if err := r.Run(":8080"); err != nil {
		slog.Error("server stopped", "err", err)
	}
}
