Rails.application.routes.draw do
  get "up" => "rails/health#show"
end
