<?php

return [
    'dsn' => env('SENTRY_LARAVEL_DSN'),
    'release' => env('SENTRY_RELEASE'),
    'environment' => env('APP_ENV', 'production'),
    'traces_sample_rate' => 1.0,
    'send_default_pii' => true,
];
