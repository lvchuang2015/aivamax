---
title: "JarveePro Campaign Settings Explained: Account Delay, Action Delay and Scheduler"
source_url: "https://blog.jarveepro.com/knowledge/Getting-Started/JarveePro-Campaign-Settings-Explained-Account-Delay,-Action-Delay-and-Scheduler/5669"
category: "knowledge"
fetched_at: "2026-05-29T15:10:21+00:00"
status_code: 200
content_hash: "3140075f541c668e4d2db5e095e9f296b4e5da30"
tags: ["jarveepro", "jarveepro/knowledge"]
---

# JarveePro Campaign Settings Explained: Account Delay, Action Delay and Scheduler

Source: [https://blog.jarveepro.com/knowledge/Getting-Started/JarveePro-Campaign-Settings-Explained-Account-Delay,-Action-Delay-and-Scheduler/5669](https://blog.jarveepro.com/knowledge/Getting-Started/JarveePro-Campaign-Settings-Explained-Account-Delay,-Action-Delay-and-Scheduler/5669)

Category: `knowledge`

## Summary

JarveePro Campaign Settings Explained: Account Delay, Action Delay and Scheduler

## Headings

- JarveePro Campaign Settings Explained: Account Delay, Action Delay and Scheduler
- Overview
- 1. Account Interval Delay (Delay Between Accounts)
- What it does
- Example
- Important Notes
- When to use
- 2. Campaign Action Delay (Delay Between Campaign Executions)
- 3. JarveePro Scheduler (Planned Execution System)
- How Scheduler works
- Major Advantages of Scheduler
- Important Scheduler Behavior Notes
- Difference Between Action Delay and Scheduler
- Best Practice Recommendations
- Example Recommended Configuration
- Common Mistakes
- Summary

## Content

JarveePro Campaign Settings Explained: Account Delay, Action Delay and Scheduler

2026-02-26

Overview

JarveePro provides multiple delay control mechanisms to ensure safe, realistic, and properly spaced automation execution. These delay systems allow you to control how frequently actions run between accounts, between campaigns, and across scheduled intervals.

There are three main delay types:

Account Delay (Account Interval Delay)

Campaign Action Delay

Scheduler (Planned Execution Delay)

Understanding the difference between these is essential for proper automation behavior.

1. Account Interval Delay (Delay Between Accounts)

What it does

This setting controls the delay between the same account executing the same campaign.

If multiple accounts are selected in a campaign, JarveePro will execute the campaign sequentially based on this delay for every accounts.

Example

If Account Interval Delay is set to

2 hours (7200 seconds)

Execution sequence:

Account 1 executes campaign

Wait 2 hours

And so on

This applies only between accounts within the same campaign.

Important Notes

Maximum value: 10,000 seconds

Only applies for the same accounts that are selected

Does not affect actions for multiple accounts

Helps prevent too many actions for the same account

When to use

Recommended when:

Managing multiple accounts

Avoiding simultaneous actions with the same accounts

Creating more natural execution patterns

2. Campaign Action Delay (Delay Between Campaign Executions)

What it does

This controls the delay between each campaign execution cycle.

This delay applies even when only one account is used.

Example

If Campaign Action Delay is set to

24 hours (86400 seconds)

Execution sequence:

Campaign executes once

Wait 24 hours

Campaign executes again

Repeat continuously

Important Notes

Maximum value: 10,000 seconds (Available on JarveePro Version

4.0.0.2

Applies per campaign

Controls campaign repetition timing

Works independently of account delay

When to use

Recommended when:

Running recurring campaigns

Automating daily actions

Preventing excessive action frequency

3. JarveePro Scheduler (Planned Execution System)

What it does

The Scheduler provides advanced control over campaign execution timing using structured schedules instead of simple delays.

Unlike Action Delay, the Scheduler can start, stop, and repeat campaigns based on defined timing rules.

How Scheduler works

Example configuration:

Schedule Type: Number of Runs

Start Time: Set specific time

Interval: Every 1 day

Total Runs: 3 times

Execution sequence:

Campaign starts at defined time

Executes 3 Times

Stops automatically after run once and waits 1 day , then start the second time.

Repeats until

Total Runs (

3 times)

is reached

Major Advantages of Scheduler

Scheduler allows:

Automatic stopping after execution

Resource optimization

Precise execution timing

Loop execution control

Fully automated operation cycles

This is more advanced and efficient than Action Delay alone.

Important Scheduler Behavior Notes

Scheduler does NOT automatically stop when running loop campaigns.

If a campaign is running and Scheduler is applied:

Scheduler controls future executions

Existing running campaigns must be manually stopped if needed

Scheduler state is managed through:

Campaign Manager → JarveePro Scheduler

Difference Between Action Delay and Scheduler

Best Practice Recommendations

For beginners:

Use Campaign Action Delay only

For advanced users:

Use Scheduler for full automation control

For large-scale automation:

Combine:

Account Interval Delay

Scheduler

Proper account limits

This creates safe and scalable automation.

Example Recommended Configuration

Safe daily automation setup:

Account Interval Delay: 300–900 seconds

Campaign Action Delay: 600

–1500

seconds

Scheduler: Every 24 hours

Execution Count: Unlimited (loop)

Common Mistakes

Most common user errors include:

Setting delay too low

Not using Scheduler

Running too many actions simultaneously

Not spacing account execution

Proper delay configuration prevents account restrictions.

Summary

JarveePro provides powerful delay control through:

Account Interval Delay

Campaign Action Delay

Scheduler

Scheduler is the most advanced and recommended method for controlling campaign timing.

Proper configuration ensures:

Safe automation

Continuous operation

Reduced risk

Scalable growth

## Extracted Links

- https://blog.jarveepro.com/Home/Blog
- https://blog.jarveepro.com/Home/KnowledgeBaseList
- https://blog.jarveepro.com/knowledge/Getting-Started/JarveePro-Campaign-Settings-Explained-Account-Delay,-Action-Delay-and-Scheduler/5669
- https://twitter.com/share?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FGetting-Started%2FJarveePro-Campaign-Settings-Explained-Account-Delay%2C-Action-Delay-and-Scheduler%2F5669
- https://www.facebook.com/jarveeproadmin
- https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FGetting-Started%2FJarveePro-Campaign-Settings-Explained-Account-Delay%2C-Action-Delay-and-Scheduler%2F5669
- https://www.jarveepro.com/
- https://www.jarveepro.com/all-features.html
- https://www.jarveepro.com/contact-us.html
- https://www.jarveepro.com/contact.html
- https://www.jarveepro.com/discord-features.html
- https://www.jarveepro.com/facebook-features.html
- https://www.jarveepro.com/get-now.html
- https://www.jarveepro.com/instagram-features.html
- https://www.jarveepro.com/linkedIn-features.html
- https://www.jarveepro.com/pinterest-features.html
- https://www.jarveepro.com/pricing.html
- https://www.jarveepro.com/reddit-features.html
- https://www.jarveepro.com/tiktok-features.html
- https://www.jarveepro.com/tumblr-features.html
- https://www.jarveepro.com/twitter-features.html
- https://www.jarveepro.com/videos-tutorials.html
- https://www.jarveepro.com/whatsapp-features.html
- https://www.jarveepro.com/youtube-features.html
- https://www.pinterest.com/pin/create/button/?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FGetting-Started%2FJarveePro-Campaign-Settings-Explained-Account-Delay%2C-Action-Delay-and-Scheduler%2F5669
