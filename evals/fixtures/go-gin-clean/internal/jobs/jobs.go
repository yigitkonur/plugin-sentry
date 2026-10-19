package jobs

import (
	"context"
	"log/slog"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Cleanup removes expired sessions.
func Cleanup(ctx context.Context, pool *pgxpool.Pool) {
	tag, err := pool.Exec(ctx, "DELETE FROM sessions WHERE expires_at < now()")
	if err != nil {
		slog.Error("cleanup failed", "err", err)
		return
	}
	slog.Info("cleanup done", "rows", tag.RowsAffected())
}
