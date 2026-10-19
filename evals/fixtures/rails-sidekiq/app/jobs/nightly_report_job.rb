class NightlyReportJob < ApplicationJob
  queue_as :default

  def perform
    Rails.logger.info("Building nightly report")
  end
end
