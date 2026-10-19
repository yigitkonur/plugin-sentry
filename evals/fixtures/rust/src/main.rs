mod routes;

#[tokio::main]
async fn main() {
    let dsn = "https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567";
    let _guard = sentry::init((
        dsn,
        sentry::ClientOptions {
            release: sentry::release_name!(),
            ..Default::default()
        },
    ));

    let app = routes::router();
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
