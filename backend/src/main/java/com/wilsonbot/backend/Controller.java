package com.wilsonbot.backend;

import com.wilsonbot.backend.entity.Sound;
import com.wilsonbot.backend.service.SoundService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;

import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;


@RestController
public class Controller {

	@Autowired
	private SoundService soundService;

	@GetMapping("/")
	public String index() {
		return "Greetings from Spring Boot!";
	}

	@GetMapping(path="sounds/{id}", produces="application/json")
    public Sound getByName(@PathVariable("id") String sound_id){
        return soundService. getByName(sound_id);
    }

}