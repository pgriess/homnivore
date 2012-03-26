all: test

test:
	nosetests-2.7 -s -w lib/homnivore --with-gae --gae-application=gae
