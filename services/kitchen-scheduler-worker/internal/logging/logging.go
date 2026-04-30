package logging

import (
	"io"
	"log/slog"
	"os"
	"strings"
)

func New(level, format string, out io.Writer) *slog.Logger {
	if out == nil {
		out = os.Stdout
	}
	options := &slog.HandlerOptions{Level: parseLevel(level)}
	if strings.EqualFold(format, "text") {
		return slog.New(slog.NewTextHandler(out, options))
	}
	return slog.New(slog.NewJSONHandler(out, options))
}

func parseLevel(level string) slog.Leveler {
	switch strings.ToUpper(strings.TrimSpace(level)) {
	case "DEBUG":
		return slog.LevelDebug
	case "WARN", "WARNING":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
