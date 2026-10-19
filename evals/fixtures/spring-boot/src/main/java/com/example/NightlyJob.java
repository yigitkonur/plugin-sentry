package com.example;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class NightlyJob {
    @Scheduled(cron = "0 0 2 * * *")
    public void run() {
        System.out.println("nightly job running");
    }
}
