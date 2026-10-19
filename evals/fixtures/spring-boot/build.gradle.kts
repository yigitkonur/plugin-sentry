plugins {
    java
    id("org.springframework.boot") version "3.3.5"
    id("io.spring.dependency-management") version "1.1.6"
    id("io.sentry.jvm.gradle") version "5.0.0"
}

group = "com.example"
version = "0.0.1"

java {
    toolchain { languageVersion.set(JavaLanguageVersion.of(21)) }
}

repositories { mavenCentral() }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("io.sentry:sentry-spring-boot-starter-jakarta:8.20.0")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}
