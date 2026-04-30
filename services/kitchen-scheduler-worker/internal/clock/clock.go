package clock

import "time"

type Clock interface {
	Now() time.Time
	Sleep(time.Duration)
}

type RealClock struct{}

func (RealClock) Now() time.Time {
	return time.Now().UTC()
}

func (RealClock) Sleep(d time.Duration) {
	time.Sleep(d)
}
